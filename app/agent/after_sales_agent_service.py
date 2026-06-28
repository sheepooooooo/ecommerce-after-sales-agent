"""Service entrypoint for the after-sales Agent.

This layer coordinates session recovery, ticket confirmation, idempotency keys
and persisted trace storage. Business tools still live under app/tools/.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from app.agent.after_sales_graph import CONTROLLED_WORKFLOW_REFUND_THEN_TICKET, build_after_sales_graph
from app.agent.response_formatter import format_agent_response
from app.services.idempotency_store import generate_idempotency_key, get_idempotency_record
from app.services.session_store import (
    SESSION_STATUS_CANCELLED,
    SESSION_STATUS_COMPLETED,
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


def _is_confirmation_query(user_query: str) -> bool:
    return (user_query or "").strip().lower() in CONFIRMATION_WORDS


def _is_cancel_query(user_query: str) -> bool:
    return (user_query or "").strip().lower() in CANCEL_WORDS


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
                answer="已取消上一轮待确认操作，本次没有写入任何模拟工单。",
                conversation_status=cleared_session["conversation_status"],
                tool_trace=[{"step": "session_control", "status": "cancelled", "created": False}],
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
    if (
        graph_result.get("answer_status") == "ticket_confirmation_required"
        and graph_result.get("intent") in {"create_ticket", CONTROLLED_WORKFLOW_REFUND_THEN_TICKET}
    ):
        order_id = graph_result.get("data", {}).get("order_id")
        if order_id:
            workflow_summary = graph_result.get("workflow_summary") or graph_result.get("data", {}).get("workflow_summary")
            workflow_type = workflow_summary.get("workflow_type") if isinstance(workflow_summary, dict) else None
            save_pending_action(
                session_id=actual_session_id,
                pending_action="create_ticket",
                pending_order_id=order_id,
                pending_payload={
                    "user_query": cleaned_query,
                    "ticket_creation_query": f"帮我给 {order_id} 创建售后工单",
                    "request_id": actual_request_id,
                    "order_id": order_id,
                    "idempotency_key": effective_key,
                    "workflow_type": workflow_type,
                    "workflow_summary": workflow_summary,
                },
            )
            graph_result["debug"] = {
                **graph_result.get("debug", {}),
                "conversation_status": "pending_confirmation",
                "pending_action": "create_ticket",
                "pending_order_id": order_id,
                "idempotency_key": effective_key,
                "workflow_type": workflow_type,
            }
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
