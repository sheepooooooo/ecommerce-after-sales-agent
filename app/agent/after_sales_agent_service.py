"""Service entrypoint for the after-sales Agent.

This layer coordinates session recovery, ticket confirmation, idempotency keys
and persisted trace storage. Business tools still live under app/tools/.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from app.agent.after_sales_graph import CONTROLLED_WORKFLOW_REFUND_THEN_TICKET, build_after_sales_graph
from app.agent.entity_extractor import extract_order_id
from app.agent.intent_classifier import classify_intent
from app.agent.response_formatter import format_agent_response
from app.services.idempotency_store import generate_idempotency_key, get_idempotency_record
from app.services.session_store import (
    SESSION_STATUS_AWAITING_ORDER_ID,
    SESSION_STATUS_CANCELLED,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_INTERRUPTED,
    SESSION_STATUS_PENDING,
    clear_pending_action,
    get_or_create_session,
    has_pending_action,
    mark_pending_action_completed,
    save_pending_action,
)
from app.services.trace_store import persist_response_trace
from app.tools.order_tool import get_ticket
from app.tools.policy_qa_tool import ask_policy_question


CONFIRMATION_WORDS = {"确认", "确认创建", "是的", "好的", "可以", "同意", "继续", "确定"}
CANCEL_WORDS = {"取消", "不用了", "不要了", "先不创建", "别创建", "撤销"}


ORDER_ID_PENDING_ACTIONS = {
    "refund_eligibility",
    "order_lookup",
    "create_ticket",
    CONTROLLED_WORKFLOW_REFUND_THEN_TICKET,
}


def _is_confirmation_query(user_query: str) -> bool:
    return (user_query or "").strip().lower() in CONFIRMATION_WORDS


def _is_cancel_query(user_query: str) -> bool:
    cleaned = (user_query or "").strip().lower()
    if cleaned in CANCEL_WORDS:
        return True
    return cleaned in {"取消", "那算了", "算了", "我不想办了", "不用了", "先不办了"}


def _is_awaiting_order_id_session(session: dict[str, Any] | None) -> bool:
    return bool(
        session
        and session.get("conversation_status") == SESSION_STATUS_AWAITING_ORDER_ID
        and session.get("pending_action") in ORDER_ID_PENDING_ACTIONS
    )


def _is_order_id_only_query(user_query: str) -> bool:
    cleaned = (user_query or "").strip()
    order_id = extract_order_id(cleaned)
    return bool(order_id and cleaned.upper() == order_id)


def _is_new_supported_request(user_query: str) -> bool:
    if extract_order_id(user_query):
        return False
    classification = classify_intent(user_query=user_query, order_id=None)
    return classification.get("intent") not in {None, "unknown"}


def _append_session_trace(response: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    response["tool_trace"] = [*response.get("tool_trace", []), event]
    return response


def _pending_payload_for_missing_order(
    user_query: str,
    intent: str,
    request_id: str,
    idempotency_key: str | None,
    workflow_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workflow_type = CONTROLLED_WORKFLOW_REFUND_THEN_TICKET if intent == CONTROLLED_WORKFLOW_REFUND_THEN_TICKET else None
    return {
        "original_intent": intent,
        "workflow_type": workflow_type,
        "fallback_ticket_requested": intent == CONTROLLED_WORKFLOW_REFUND_THEN_TICKET,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "query_length": len(user_query or ""),
        "workflow_summary": workflow_summary,
    }


def _restored_query_from_pending(pending_action: str, order_id: str, pending_payload: dict[str, Any]) -> str:
    if pending_action == "refund_eligibility":
        return f"帮我判断订单 {order_id} 是否支持退款"
    if pending_action == "order_lookup":
        return f"帮我查询订单 {order_id} 的状态"
    if pending_action == "create_ticket":
        return f"帮我给订单 {order_id} 创建售后工单"
    if pending_action == CONTROLLED_WORKFLOW_REFUND_THEN_TICKET:
        return f"订单 {order_id} 能退吗，如果不能退就帮我创建售后工单"
    return f"{pending_payload.get('original_intent') or ''} {order_id}".strip()


def _finalize_response(response: dict[str, Any]) -> dict[str, Any]:
    """Persist sanitized trace after the response is already shaped."""
    trace_events = persist_response_trace(response)
    response.setdefault("debug", {})
    response["debug"]["trace_event_count"] = len(trace_events)
    return response


def _format_session_control_response(
    request_id: str,
    session_id: str,
    user_query: str,
    answer: str,
    conversation_status: str,
    tool_trace: list[dict[str, Any]],
    data_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return format_agent_response(
        {
            "request_id": request_id,
            "session_id": session_id,
            "user_query": user_query,
            "intent": "session_control",
            "intent_reason": "用户输入为会话确认或取消指令，由持久化 session 状态处理。",
            "tool_used": None,
            "answer_status": "answered",
            "answer": answer,
            "data": {"conversation_status": conversation_status, **(data_extra or {})},
            "citations": [],
            "needs_human_review": False,
            "confirmation_required": False,
            "tool_trace": tool_trace,
            "error": None,
            "debug": {"session_id": session_id, "conversation_status": conversation_status},
        }
    )


def _build_reused_ticket_response(
    request_id: str,
    session_id: str,
    user_query: str,
    ticket: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    return format_agent_response(
        {
            "request_id": request_id,
            "session_id": session_id,
            "user_query": user_query,
            "intent": "session_control",
            "intent_reason": "重复确认命中已完成的幂等记录，返回已有模拟工单结果。",
            "tool_used": "order_tool.create_ticket",
            "answer_status": "answered",
            "answer": f"该待确认操作已经创建过模拟工单，本次返回同一工单号：{ticket['ticket_id']}。",
            "data": {
                "ticket": ticket,
                "conversation_status": SESSION_STATUS_COMPLETED,
                "idempotency_reused": True,
            },
            "citations": [],
            "needs_human_review": False,
            "confirmation_required": False,
            "tool_trace": [
                {
                    "step": "order_tool.create_ticket",
                    "status": "success",
                    "latency_ms": 0,
                    "ticket_id": ticket["ticket_id"],
                    "idempotency_key": idempotency_key,
                    "idempotency_reused": True,
                }
            ],
            "error": None,
            "debug": {
                "session_id": session_id,
                "conversation_status": SESSION_STATUS_COMPLETED,
                "idempotency_key": idempotency_key,
                "idempotency_reused": True,
            },
        }
    )


def _try_reuse_completed_ticket(
    request_id: str,
    session_id: str,
    user_query: str,
    idempotency_key: str | None,
) -> dict[str, Any] | None:
    if not idempotency_key:
        return None
    record = get_idempotency_record(idempotency_key)
    if not record or record.get("status") != "completed" or not record.get("ticket_id"):
        return None
    ticket = get_ticket(int(record["ticket_id"]))
    if ticket is None:
        return None
    return _build_reused_ticket_response(
        request_id=request_id,
        session_id=session_id,
        user_query=user_query,
        ticket=ticket,
        idempotency_key=idempotency_key,
    )


def _save_missing_order_pending_if_needed(
    response: dict[str, Any],
    session_id: str,
    user_query: str,
    request_id: str,
    idempotency_key: str | None,
) -> dict[str, Any]:
    intent = response.get("intent")
    if response.get("answer_status") != "missing_order_id" or intent not in ORDER_ID_PENDING_ACTIONS:
        return response

    workflow_summary = response.get("workflow_summary") or response.get("data", {}).get("workflow_summary")
    save_pending_action(
        session_id=session_id,
        pending_action=str(intent),
        pending_order_id=None,
        pending_payload=_pending_payload_for_missing_order(
            user_query=user_query,
            intent=str(intent),
            request_id=request_id,
            idempotency_key=idempotency_key,
            workflow_summary=workflow_summary if isinstance(workflow_summary, dict) else None,
        ),
        pending_reason="missing_order_id",
        workflow_type=CONTROLLED_WORKFLOW_REFUND_THEN_TICKET if intent == CONTROLLED_WORKFLOW_REFUND_THEN_TICKET else None,
        conversation_status=SESSION_STATUS_AWAITING_ORDER_ID,
    )
    response.setdefault("debug", {})
    response["debug"] = {
        **response["debug"],
        "conversation_status": SESSION_STATUS_AWAITING_ORDER_ID,
        "pending_action": intent,
        "pending_reason": "missing_order_id",
    }
    return _append_session_trace(
        response,
        {
            "step": "session_store.save_pending_action",
            "action_type": "pending_task_created",
            "status": "success",
            "pending_action": intent,
            "pending_reason": "missing_order_id",
            "workflow_type": CONTROLLED_WORKFLOW_REFUND_THEN_TICKET
            if intent == CONTROLLED_WORKFLOW_REFUND_THEN_TICKET
            else None,
            "latency_ms": 0,
        },
    )


def _save_ticket_confirmation_pending_if_needed(
    graph_result: dict[str, Any],
    session_id: str,
    user_query: str,
    request_id: str,
    idempotency_key: str | None,
) -> dict[str, Any]:
    if (
        graph_result.get("answer_status") != "ticket_confirmation_required"
        or graph_result.get("intent") not in {"create_ticket", CONTROLLED_WORKFLOW_REFUND_THEN_TICKET}
    ):
        return graph_result

    order_id = graph_result.get("data", {}).get("order_id")
    if not order_id:
        return graph_result

    workflow_summary = graph_result.get("workflow_summary") or graph_result.get("data", {}).get("workflow_summary")
    workflow_type = workflow_summary.get("workflow_type") if isinstance(workflow_summary, dict) else None
    save_pending_action(
        session_id=session_id,
        pending_action="create_ticket",
        pending_order_id=order_id,
        pending_payload={
            "user_query": user_query,
            "ticket_creation_query": f"帮我给 {order_id} 创建售后工单",
            "request_id": request_id,
            "order_id": order_id,
            "idempotency_key": idempotency_key,
            "workflow_type": workflow_type,
            "workflow_summary": workflow_summary,
        },
        pending_reason="awaiting_confirmation",
        workflow_type=workflow_type,
        conversation_status=SESSION_STATUS_PENDING,
    )
    graph_result["debug"] = {
        **graph_result.get("debug", {}),
        "conversation_status": SESSION_STATUS_PENDING,
        "pending_action": "create_ticket",
        "pending_order_id": order_id,
        "idempotency_key": idempotency_key,
        "workflow_type": workflow_type,
    }
    return _append_session_trace(
        graph_result,
        {
            "step": "session_store.save_pending_action",
            "action_type": "pending_task_created",
            "status": "success",
            "pending_action": "create_ticket",
            "pending_order_id": order_id,
            "pending_reason": "awaiting_confirmation",
            "workflow_type": workflow_type,
            "latency_ms": 0,
        },
    )


def _resume_pending_order_id_task(
    session: dict[str, Any],
    order_id: str,
    user_query: str,
    request_id: str,
    session_id: str,
    idempotency_key: str | None,
    policy_qa_callable: Callable[..., dict[str, Any]] | None,
) -> dict[str, Any]:
    pending_action = str(session.get("pending_action") or "")
    pending_payload = session.get("pending_payload") or {}
    restored_query = _restored_query_from_pending(pending_action, order_id, pending_payload)
    effective_key = idempotency_key or pending_payload.get("idempotency_key") or generate_idempotency_key()
    graph_result = _invoke_after_sales_graph(
        user_query=restored_query,
        confirm_ticket_creation=False,
        request_id=request_id,
        session_id=session_id,
        idempotency_key=effective_key,
        policy_qa_callable=policy_qa_callable,
        debug_extra={
            "restored_from_session": True,
            "resumed_action": pending_action,
            "resumed_order_id": order_id,
            "previous_pending_reason": session.get("pending_reason"),
            "workflow_type": pending_payload.get("workflow_type"),
        },
    )
    graph_result["user_query"] = user_query
    graph_result.setdefault("debug", {})
    graph_result["debug"] = {
        **graph_result["debug"],
        "restored_from_session": True,
        "resumed_action": pending_action,
        "resumed_order_id": order_id,
    }
    graph_result = _append_session_trace(
        graph_result,
        {
            "step": "session_store.resume_pending_action",
            "action_type": "pending_task_resumed",
            "status": "success",
            "resumed_action": pending_action,
            "resumed_order_id": order_id,
            "pending_reason": session.get("pending_reason"),
            "workflow_type": pending_payload.get("workflow_type"),
            "latency_ms": 0,
        },
    )
    graph_result = _save_ticket_confirmation_pending_if_needed(
        graph_result=graph_result,
        session_id=session_id,
        user_query=restored_query,
        request_id=request_id,
        idempotency_key=effective_key,
    )
    if graph_result.get("answer_status") != "ticket_confirmation_required":
        clear_pending_action(session_id, SESSION_STATUS_COMPLETED)
        graph_result["debug"] = {
            **graph_result.get("debug", {}),
            "conversation_status": SESSION_STATUS_COMPLETED,
        }
    return graph_result


def run_after_sales_agent(
    user_query: str,
    confirm_ticket_creation: bool = False,
    request_id: str | None = None,
    policy_qa_callable: Callable[..., dict[str, Any]] | None = None,
    session_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Run one Agent request and persist a sanitized execution trace."""
    actual_request_id = request_id or str(uuid4())
    cleaned_query = (user_query or "").strip()
    session = get_or_create_session(session_id)
    actual_session_id = session["session_id"]
    cleaned_idempotency_key = (idempotency_key or "").strip() or None

    if not cleaned_query:
        return _finalize_response(
            format_agent_response(
                {
                    "request_id": actual_request_id,
                    "session_id": actual_session_id,
                    "user_query": user_query or "",
                    "intent": "unknown",
                    "intent_reason": "用户输入为空。",
                    "tool_used": None,
                    "answer_status": "unknown_request",
                    "answer": "请输入需要处理的售后问题。",
                    "citations": [],
                    "needs_human_review": False,
                    "confirmation_required": False,
                    "tool_trace": [{"step": "receive_request", "status": "empty_input"}],
                    "error": None,
                    "debug": {},
                }
            )
        )

    if _is_cancel_query(cleaned_query):
        if has_pending_action(session):
            cleared_session = clear_pending_action(actual_session_id, SESSION_STATUS_CANCELLED)
            response = _format_session_control_response(
                request_id=actual_request_id,
                session_id=actual_session_id,
                user_query=cleaned_query,
                answer="已取消上一轮待补充或待确认的任务，本次没有写入任何模拟工单。",
                conversation_status=cleared_session["conversation_status"],
                tool_trace=[
                    {
                        "step": "session_control",
                        "action_type": "pending_task_cancelled",
                        "status": "cancelled",
                        "created": False,
                        "pending_action": session.get("pending_action"),
                    }
                ],
            )
            return _finalize_response(response)
        response = _format_session_control_response(
            request_id=actual_request_id,
            session_id=actual_session_id,
            user_query=cleaned_query,
            answer="当前没有待确认操作，无需取消。",
            conversation_status=session["conversation_status"],
            tool_trace=[{"step": "session_control", "status": "no_pending_action"}],
        )
        return _finalize_response(response)

    if _is_awaiting_order_id_session(session):
        supplied_order_id = extract_order_id(cleaned_query)
        if supplied_order_id and _is_order_id_only_query(cleaned_query):
            response = _resume_pending_order_id_task(
                session=session,
                order_id=supplied_order_id,
                user_query=cleaned_query,
                request_id=actual_request_id,
                session_id=actual_session_id,
                idempotency_key=cleaned_idempotency_key,
                policy_qa_callable=policy_qa_callable,
            )
            return _finalize_response(response)

        if _is_new_supported_request(cleaned_query):
            clear_pending_action(actual_session_id, SESSION_STATUS_INTERRUPTED)
            effective_key = cleaned_idempotency_key or generate_idempotency_key()
            graph_result = _invoke_after_sales_graph(
                user_query=cleaned_query,
                confirm_ticket_creation=confirm_ticket_creation,
                request_id=actual_request_id,
                session_id=actual_session_id,
                idempotency_key=effective_key,
                policy_qa_callable=policy_qa_callable,
                debug_extra={
                    "pending_task_interrupted": True,
                    "interrupted_pending_action": session.get("pending_action"),
                },
            )
            graph_result = _append_session_trace(
                graph_result,
                {
                    "step": "session_store.interrupt_pending_action",
                    "action_type": "pending_task_interrupted",
                    "status": "interrupted",
                    "pending_action": session.get("pending_action"),
                    "latency_ms": 0,
                },
            )
            graph_result = _save_missing_order_pending_if_needed(
                response=graph_result,
                session_id=actual_session_id,
                user_query=cleaned_query,
                request_id=actual_request_id,
                idempotency_key=effective_key,
            )
            graph_result = _save_ticket_confirmation_pending_if_needed(
                graph_result=graph_result,
                session_id=actual_session_id,
                user_query=cleaned_query,
                request_id=actual_request_id,
                idempotency_key=effective_key,
            )
            return _finalize_response(graph_result)

    if _is_confirmation_query(cleaned_query):
        pending_payload = session.get("pending_payload") or {}
        payload_key = cleaned_idempotency_key or pending_payload.get("idempotency_key")
        if not has_pending_action(session, "create_ticket"):
            reused = _try_reuse_completed_ticket(
                request_id=actual_request_id,
                session_id=actual_session_id,
                user_query=cleaned_query,
                idempotency_key=payload_key,
            )
            if reused:
                return _finalize_response(reused)
            response = _format_session_control_response(
                request_id=actual_request_id,
                session_id=actual_session_id,
                user_query=cleaned_query,
                answer="当前没有待确认操作，未创建任何模拟工单。",
                conversation_status=session["conversation_status"],
                tool_trace=[{"step": "session_control", "status": "no_pending_action"}],
            )
            return _finalize_response(response)

        restored_query = pending_payload.get("user_query") or cleaned_query
        if pending_payload.get("workflow_type") == CONTROLLED_WORKFLOW_REFUND_THEN_TICKET:
            restored_query = pending_payload.get("ticket_creation_query") or restored_query
        effective_key = payload_key or generate_idempotency_key()
        graph_result = _invoke_after_sales_graph(
            user_query=restored_query,
            confirm_ticket_creation=True,
            request_id=actual_request_id,
            session_id=actual_session_id,
            idempotency_key=effective_key,
            policy_qa_callable=policy_qa_callable,
            debug_extra={
                "restored_from_session": True,
                "pending_order_id": session.get("pending_order_id"),
                "idempotency_key": effective_key,
                "workflow_type": pending_payload.get("workflow_type"),
            },
        )
        if graph_result.get("tool_used") == "order_tool.create_ticket":
            ticket = graph_result.get("data", {}).get("ticket") or {}
            mark_pending_action_completed(
                actual_session_id,
                {
                    "last_completed_action": "create_ticket",
                    "last_ticket_id": ticket.get("ticket_id"),
                    "idempotency_key": effective_key,
                },
            )
            graph_result["debug"] = {
                **graph_result.get("debug", {}),
                "conversation_status": SESSION_STATUS_COMPLETED,
                "idempotency_key": effective_key,
            }
        return _finalize_response(graph_result)

    effective_key = cleaned_idempotency_key or generate_idempotency_key()
    graph_result = _invoke_after_sales_graph(
        user_query=cleaned_query,
        confirm_ticket_creation=confirm_ticket_creation,
        request_id=actual_request_id,
        session_id=actual_session_id,
        idempotency_key=effective_key,
        policy_qa_callable=policy_qa_callable,
    )
    graph_result = _save_missing_order_pending_if_needed(
        response=graph_result,
        session_id=actual_session_id,
        user_query=cleaned_query,
        request_id=actual_request_id,
        idempotency_key=effective_key,
    )
    graph_result = _save_ticket_confirmation_pending_if_needed(
        graph_result=graph_result,
        session_id=actual_session_id,
        user_query=cleaned_query,
        request_id=actual_request_id,
        idempotency_key=effective_key,
    )
    return _finalize_response(graph_result)


def _invoke_after_sales_graph(
    user_query: str,
    confirm_ticket_creation: bool,
    request_id: str,
    session_id: str,
    idempotency_key: str | None,
    policy_qa_callable: Callable[..., dict[str, Any]] | None = None,
    debug_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    graph = build_after_sales_graph()
    initial_state = {
        "request_id": request_id,
        "session_id": session_id,
        "user_query": user_query,
        "confirm_ticket_creation": confirm_ticket_creation,
        "idempotency_key": idempotency_key,
        "policy_qa_callable": policy_qa_callable or ask_policy_question,
        "tool_trace": [],
        "citations": [],
        "debug": {
            "session_id": session_id,
            "idempotency_key": idempotency_key,
            **(debug_extra or {}),
        },
        "error": None,
    }
    final_state = graph.invoke(initial_state)
    response = final_state.get("formatted_response") or format_agent_response(final_state)
    response["session_id"] = session_id
    response.setdefault("debug", {})
    response["debug"]["idempotency_key"] = idempotency_key
    return response
