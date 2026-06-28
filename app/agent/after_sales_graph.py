"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

# ============================================================
# 【核心文件分区】
# 1. 路径与依赖：导入本文件需要的模块。
# 2. 数据结构与辅助函数：定义本模块内部复用的工具。
# 3. 核心流程：实现本文件最重要的业务或工程能力。
# 4. 边界与阅读重点：说明副作用、异常和学习入口。
# ============================================================


from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.agent_state import AfterSalesAgentState
from app.agent.entity_extractor import extract_order_id, extract_order_ids
from app.agent.intent_classifier import classify_intent
from app.agent.response_formatter import format_agent_response
from app.services.idempotency_store import (
    IDEMPOTENCY_STATUS_COMPLETED,
    complete_idempotency_record,
    create_or_get_pending_record,
    generate_idempotency_key,
)
from app.tools.order_tool import create_ticket, get_order, get_ticket
from app.tools.policy_qa_tool import ask_policy_question
from app.tools.refund_eligibility_tool import check_refund_eligibility
from app.observability.trace_utils import ToolCallError, measure_tool_call


CONTROLLED_WORKFLOW_REFUND_THEN_TICKET = "refund_then_ticket_if_ineligible"
CONTROLLED_WORKFLOW_MAX_STEPS = 6
CONTROLLED_WORKFLOW_TASK_PLAN = [
    "extract_order_id",
    "lookup_order",
    "check_refund_eligibility",
    "decide_ticket_fallback",
]


def _append_trace(state: dict[str, Any], event: dict[str, Any]) -> list[dict[str, Any]]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return [*state.get("tool_trace", []), event]


def receive_request_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return {
        "tool_trace": _append_trace(state, {"step": "receive_request", "status": "success"}),
        "debug": {
            **state.get("debug", {}),
            "confirm_ticket_creation": state.get("confirm_ticket_creation", False),
        },
    }


def extract_entities_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    user_query = state.get("user_query", "")
    all_order_ids = extract_order_ids(user_query)
    first_order_id = extract_order_id(user_query)
    return {
        "order_id": first_order_id,
        "all_detected_order_ids": all_order_ids,
        "tool_trace": _append_trace(
            state,
            {
                "step": "extract_entities",
                "status": "success",
                "order_id": first_order_id,
                "all_detected_order_ids": all_order_ids,
            },
        ),
        "debug": {
            **state.get("debug", {}),
            "all_detected_order_ids": all_order_ids,
        },
    }


def classify_intent_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    classification = classify_intent(
        user_query=state.get("user_query", ""),
        order_id=state.get("order_id"),
    )
    return {
        "intent": classification["intent"],
        "intent_reason": classification["reason"],
        "requires_order_id": classification["requires_order_id"],
        "tool_trace": _append_trace(
            state,
            {
                "step": "classify_intent",
                "status": "success",
                "intent": classification["intent"],
                "confidence": classification["confidence"],
            },
        ),
        "debug": {
            **state.get("debug", {}),
            "intent_classification": classification,
        },
    }


def route_after_classification(state: AfterSalesAgentState) -> str:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    intent = state.get("intent", "unknown")
    order_id = state.get("order_id")

    if intent in {"order_lookup", "refund_eligibility", "create_ticket", CONTROLLED_WORKFLOW_REFUND_THEN_TICKET} and not order_id:
        return "ask_for_order_id"
    if intent == CONTROLLED_WORKFLOW_REFUND_THEN_TICKET:
        return CONTROLLED_WORKFLOW_REFUND_THEN_TICKET
    if intent == "create_ticket" and not state.get("confirm_ticket_creation", False):
        return "ticket_confirmation"
    if intent == "create_ticket":
        return "create_ticket"
    if intent in {"policy_qa", "order_lookup", "refund_eligibility", "human_handoff"}:
        return intent
    return "unknown"


def ask_for_order_id_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return {
        "answer_status": "missing_order_id",
        "answer": "请提供订单号后我再继续处理，格式类似 ORD10003。",
        "tool_used": None,
        "confirmation_required": False,
        "needs_human_review": False,
        "tool_trace": _append_trace(
            state,
            {"step": "ask_for_order_id", "status": "success"},
        ),
    }


def policy_qa_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    policy_callable: Callable[..., dict[str, Any]] = state.get("policy_qa_callable") or ask_policy_question
    try:
        result, tool_trace = measure_tool_call(
            "policy_qa_tool",
            policy_callable,
            state.get("user_query", ""),
        )
        answer_status = "answered"
        error = None
        if result.get("answer_status") == "degraded":
            answer_status = "degraded"
        elif result.get("answer_status") == "generation_error" or result.get("success") is False:
            answer_status = "tool_error"
            error = result.get("error") or result.get("message")
            tool_trace = {**tool_trace, "status": "error"}
        retry_events = result.get("debug", {}).get("retry_trace_events", [])
        retry_count = int(result.get("debug", {}).get("retry_count") or 0)
        tool_trace = {
            **tool_trace,
            "retry_count": retry_count,
            "error_category": result.get("debug", {}).get("error_category"),
            "fallback_action": result.get("debug", {}).get("fallback_action"),
            "degraded": result.get("debug", {}).get("degraded", False),
        }
        return {
            "policy_qa_result": result,
            "tool_used": "policy_qa_tool.ask_policy_question",
            "answer_status": answer_status,
            "answer": result.get("answer", ""),
            "citations": result.get("citations", []),
            "needs_human_review": result.get("answer_status") == "manual_review",
            "degraded": result.get("answer_status") == "degraded",
            "fallback_action": result.get("debug", {}).get("fallback_action"),
            "retry_count": retry_count,
            "error_category": result.get("debug", {}).get("error_category"),
            "error": error,
            "debug": {
                **state.get("debug", {}),
                "policy_qa": result.get("debug", {}),
                "grounding_verification": result.get("grounding_verification"),
            },
            "tool_trace": _append_trace(
                state,
                tool_trace,
            ) + retry_events,
        }
    except ToolCallError as error:
        return _tool_error_update(state, "policy_qa_tool", error.original_error, error.trace)
    except Exception as error:
        return _tool_error_update(state, "policy_qa_tool", error)


def order_lookup_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    try:
        order, tool_trace = measure_tool_call(
            "order_tool.get_order",
            get_order,
            state.get("order_id", ""),
        )
        tool_trace["found"] = order is not None
        return {
            "order_result": order,
            "tool_used": "order_tool.get_order",
            "answer_status": "manual_review" if order is None else "answered",
            "needs_human_review": order is None,
            "tool_trace": _append_trace(
                state,
                tool_trace,
            ),
        }
    except ToolCallError as error:
        return _tool_error_update(state, "order_tool.get_order", error.original_error, error.trace)
    except Exception as error:
        return _tool_error_update(state, "order_tool.get_order", error)


def refund_eligibility_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    try:
        result, tool_trace = measure_tool_call(
            "refund_eligibility_tool.check_refund_eligibility",
            check_refund_eligibility,
            state.get("order_id", ""),
        )
        needs_human_review = result.get("decision") == "manual_review"
        tool_trace["decision"] = result.get("decision")
        return {
            "refund_result": result,
            "tool_used": "refund_eligibility_tool.check_refund_eligibility",
            "answer_status": "manual_review" if needs_human_review else "answered",
            "needs_human_review": needs_human_review,
            "tool_trace": _append_trace(
                state,
                tool_trace,
            ),
        }
    except ToolCallError as error:
        return _tool_error_update(
            state,
            "refund_eligibility_tool.check_refund_eligibility",
            error.original_error,
            error.trace,
        )
    except Exception as error:
        return _tool_error_update(state, "refund_eligibility_tool.check_refund_eligibility", error)


def _workflow_trace_event(
    action_type: str,
    current_step: str,
    status: str = "success",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "step": current_step,
        "action_type": action_type,
        "status": status,
        "workflow_type": CONTROLLED_WORKFLOW_REFUND_THEN_TICKET,
        **extra,
    }


def _workflow_summary(
    plan_status: str,
    current_step: str,
    executed_steps: list[str],
    fallback_requested: bool,
    next_action: str,
    decision_reason: str,
) -> dict[str, Any]:
    return {
        "workflow_type": CONTROLLED_WORKFLOW_REFUND_THEN_TICKET,
        "task_plan": CONTROLLED_WORKFLOW_TASK_PLAN,
        "current_step": current_step,
        "plan_status": plan_status,
        "fallback_requested": fallback_requested,
        "next_action": next_action,
        "max_steps": CONTROLLED_WORKFLOW_MAX_STEPS,
        "executed_steps": executed_steps,
        "decision_reason": decision_reason,
    }


def refund_then_ticket_workflow_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """Run a fixed refund-then-ticket-fallback workflow without writing tickets."""
    order_id = state.get("order_id")
    executed_steps: list[str] = ["extract_order_id"]
    trace = _append_trace(
        state,
        _workflow_trace_event(
            "plan_created",
            "workflow_plan",
            task_plan=CONTROLLED_WORKFLOW_TASK_PLAN,
            max_steps=CONTROLLED_WORKFLOW_MAX_STEPS,
        ),
    )

    try:
        current_step = "lookup_order"
        trace.append(_workflow_trace_event("plan_step_started", current_step))
        order, order_trace = measure_tool_call("order_tool.get_order", get_order, order_id or "")
        order_trace["found"] = order is not None
        trace.append(order_trace)
        executed_steps.append(current_step)
        trace.append(
            _workflow_trace_event(
                "plan_step_completed",
                current_step,
                found=order is not None,
            )
        )

        if order is None:
            decision_reason = f"未查询到订单 {order_id}，停止复合流程，不保存工单待确认动作。"
            summary = _workflow_summary(
                plan_status="stopped",
                current_step=current_step,
                executed_steps=executed_steps,
                fallback_requested=True,
                next_action="stop_order_not_found",
                decision_reason=decision_reason,
            )
            trace.append(_workflow_trace_event("plan_stopped", current_step, reason=decision_reason))
            return {
                "order_result": None,
                "tool_used": "order_tool.get_order",
                "answer_status": "manual_review",
                "answer": decision_reason,
                "needs_human_review": True,
                "confirmation_required": False,
                "workflow_type": CONTROLLED_WORKFLOW_REFUND_THEN_TICKET,
                "task_plan": CONTROLLED_WORKFLOW_TASK_PLAN,
                "current_step": current_step,
                "plan_status": "stopped",
                "fallback_requested": True,
                "next_action": "stop_order_not_found",
                "max_steps": CONTROLLED_WORKFLOW_MAX_STEPS,
                "executed_steps": executed_steps,
                "workflow_summary": summary,
                "data": {"order_id": order_id, "workflow_summary": summary},
                "tool_trace": trace,
            }

        current_step = "check_refund_eligibility"
        trace.append(_workflow_trace_event("plan_step_started", current_step))
        refund_result, refund_trace = measure_tool_call(
            "refund_eligibility_tool.check_refund_eligibility",
            check_refund_eligibility,
            order_id or "",
        )
        refund_trace["decision"] = refund_result.get("decision")
        trace.append(refund_trace)
        executed_steps.append(current_step)
        trace.append(
            _workflow_trace_event(
                "plan_step_completed",
                current_step,
                decision=refund_result.get("decision"),
            )
        )

        decision = refund_result.get("decision")
        reason = str(refund_result.get("reason") or "")
        if decision == "eligible":
            decision_reason = "退款资格判断为可退款，复合流程在退款资格结果处结束，不进入工单创建。"
            summary = _workflow_summary(
                plan_status="completed",
                current_step="decide_ticket_fallback",
                executed_steps=[*executed_steps, "decide_ticket_fallback"],
                fallback_requested=True,
                next_action="refund_eligible_no_ticket",
                decision_reason=decision_reason,
            )
            trace.append(
                _workflow_trace_event(
                    "plan_decision",
                    "decide_ticket_fallback",
                    decision="refund_eligible_no_ticket",
                    reason=decision_reason,
                )
            )
            trace.append(_workflow_trace_event("plan_completed", "decide_ticket_fallback"))
            return {
                "order_result": order,
                "refund_result": refund_result,
                "tool_used": "refund_eligibility_tool.check_refund_eligibility",
                "answer_status": "answered",
                "answer": f"订单 {order_id} 当前规则判断为可退款，因此不创建售后工单。原因：{reason}",
                "needs_human_review": False,
                "confirmation_required": False,
                "workflow_type": CONTROLLED_WORKFLOW_REFUND_THEN_TICKET,
                "task_plan": CONTROLLED_WORKFLOW_TASK_PLAN,
                "current_step": "decide_ticket_fallback",
                "plan_status": "completed",
                "fallback_requested": True,
                "next_action": "refund_eligible_no_ticket",
                "max_steps": CONTROLLED_WORKFLOW_MAX_STEPS,
                "executed_steps": summary["executed_steps"],
                "workflow_summary": summary,
                "data": {
                    "order_id": order_id,
                    "refund_result": refund_result,
                    "workflow_summary": summary,
                },
                "tool_trace": trace,
            }

        if decision == "not_eligible":
            decision_reason = "退款资格判断为不可直接退款，且用户明确要求不符合时创建工单，进入写库前确认。"
            summary = _workflow_summary(
                plan_status="waiting_confirmation",
                current_step="decide_ticket_fallback",
                executed_steps=[*executed_steps, "decide_ticket_fallback"],
                fallback_requested=True,
                next_action="confirm_create_ticket",
                decision_reason=decision_reason,
            )
            trace.append(
                _workflow_trace_event(
                    "plan_decision",
                    "decide_ticket_fallback",
                    decision="wait_for_ticket_confirmation",
                    reason=decision_reason,
                )
            )
            trace.append(_workflow_trace_event("plan_waiting_confirmation", "decide_ticket_fallback"))
            return {
                "order_result": order,
                "refund_result": refund_result,
                "tool_used": "refund_eligibility_tool.check_refund_eligibility",
                "answer_status": "ticket_confirmation_required",
                "answer": (
                    f"订单 {order_id} 当前规则判断为不可直接退款。原因：{reason} "
                    "如果继续创建模拟售后工单，将写入本地模拟数据库。请明确确认后再继续。"
                ),
                "needs_human_review": False,
                "confirmation_required": True,
                "workflow_type": CONTROLLED_WORKFLOW_REFUND_THEN_TICKET,
                "task_plan": CONTROLLED_WORKFLOW_TASK_PLAN,
                "current_step": "decide_ticket_fallback",
                "plan_status": "waiting_confirmation",
                "fallback_requested": True,
                "next_action": "confirm_create_ticket",
                "max_steps": CONTROLLED_WORKFLOW_MAX_STEPS,
                "executed_steps": summary["executed_steps"],
                "workflow_summary": summary,
                "data": {
                    "order_id": order_id,
                    "refund_result": refund_result,
                    "confirm_ticket_creation": False,
                    "workflow_summary": summary,
                },
                "tool_trace": trace,
            }

        decision_reason = "退款资格判断需要人工处理，复合流程停止，不自动进入工单创建。"
        summary = _workflow_summary(
            plan_status="stopped",
            current_step="decide_ticket_fallback",
            executed_steps=[*executed_steps, "decide_ticket_fallback"],
            fallback_requested=True,
            next_action="human_review",
            decision_reason=decision_reason,
        )
        trace.append(_workflow_trace_event("plan_stopped", "decide_ticket_fallback", reason=decision_reason))
        return {
            "order_result": order,
            "refund_result": refund_result,
            "tool_used": "refund_eligibility_tool.check_refund_eligibility",
            "answer_status": "manual_review",
            "answer": f"{decision_reason} 原因：{reason}",
            "needs_human_review": True,
            "confirmation_required": False,
            "workflow_type": CONTROLLED_WORKFLOW_REFUND_THEN_TICKET,
            "task_plan": CONTROLLED_WORKFLOW_TASK_PLAN,
            "current_step": "decide_ticket_fallback",
            "plan_status": "stopped",
            "fallback_requested": True,
            "next_action": "human_review",
            "max_steps": CONTROLLED_WORKFLOW_MAX_STEPS,
            "executed_steps": summary["executed_steps"],
            "workflow_summary": summary,
            "data": {
                "order_id": order_id,
                "refund_result": refund_result,
                "workflow_summary": summary,
            },
            "tool_trace": trace,
        }
    except ToolCallError as error:
        return _tool_error_update(state, "controlled_workflow", error.original_error, error.trace)
    except Exception as error:
        return _tool_error_update(state, "controlled_workflow", error)


def ticket_confirmation_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return {
        "answer_status": "ticket_confirmation_required",
        "answer": (
            "系统尚未创建工单。创建模拟售后工单会写入本地数据库，"
            "请明确确认后我才会继续创建。"
        ),
        "tool_used": None,
        "confirmation_required": True,
        "needs_human_review": False,
        "tool_trace": _append_trace(
            state,
            {"step": "ticket_confirmation", "status": "success", "created": False},
        ),
    }


def create_ticket_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    if not state.get("confirm_ticket_creation", False):
        return ticket_confirmation_node(state)
    try:
        idempotency_key = (
            state.get("idempotency_key")
            or state.get("debug", {}).get("idempotency_key")
            or generate_idempotency_key()
        )
        idempotency_record = create_or_get_pending_record(
            idempotency_key=idempotency_key,
            session_id=state.get("session_id", ""),
            action_type="create_ticket",
            order_id=state.get("order_id"),
        )
        if idempotency_record.get("status") == IDEMPOTENCY_STATUS_COMPLETED:
            existing_ticket = get_ticket(int(idempotency_record["ticket_id"]))
            if existing_ticket is None:
                raise RuntimeError("idempotency record references a missing ticket")
            return {
                "ticket_result": existing_ticket,
                "tool_used": "order_tool.create_ticket",
                "answer_status": "answered",
                "confirmation_required": False,
                "needs_human_review": False,
                "debug": {
                    **state.get("debug", {}),
                    "idempotency_key": idempotency_key,
                    "idempotency_reused": True,
                },
                "tool_trace": _append_trace(
                    state,
                    {
                        "step": "order_tool.create_ticket",
                        "status": "success",
                        "latency_ms": 0,
                        "ticket_id": existing_ticket.get("ticket_id"),
                        "idempotency_key": idempotency_key,
                        "idempotency_reused": True,
                    },
                ),
            }

        ticket, tool_trace = measure_tool_call(
            "order_tool.create_ticket",
            create_ticket,
            order_id=state.get("order_id"),
            issue_type="after_sales_request",
            description=state.get("user_query", ""),
        )
        complete_idempotency_record(idempotency_key, int(ticket.get("ticket_id")))
        tool_trace["ticket_id"] = ticket.get("ticket_id")
        tool_trace["idempotency_key"] = idempotency_key
        tool_trace["idempotency_reused"] = False
        return {
            "ticket_result": ticket,
            "tool_used": "order_tool.create_ticket",
            "answer_status": "answered",
            "confirmation_required": False,
            "needs_human_review": False,
            "debug": {
                **state.get("debug", {}),
                "idempotency_key": idempotency_key,
                "idempotency_reused": False,
            },
            "tool_trace": _append_trace(
                state,
                tool_trace,
            ),
        }
    except ToolCallError as error:
        return _tool_error_update(state, "order_tool.create_ticket", error.original_error, error.trace)
    except Exception as error:
        return _tool_error_update(state, "order_tool.create_ticket", error)


def human_handoff_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return {
        "answer_status": "manual_review",
        "answer": (
            "这个问题可能涉及账户安全、资金争议、隐私或强投诉，建议转人工处理。"
            "请只提供订单号、支付时间、问题现象等非敏感信息，"
            "不要发送密码、验证码、银行卡完整号等敏感信息。"
            "当前仅给出模拟人工处理建议，不执行真实客服转接。"
        ),
        "tool_used": None,
        "needs_human_review": True,
        "confirmation_required": False,
        "tool_trace": _append_trace(
            state,
            {"step": "human_handoff", "status": "success"},
        ),
    }


def unknown_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    return {
        "answer_status": "unknown_request",
        "answer": "当前 Agent 只能处理政策咨询、订单查询、退款资格判断和模拟工单创建。",
        "tool_used": None,
        "needs_human_review": False,
        "confirmation_required": False,
        "tool_trace": _append_trace(state, {"step": "unknown", "status": "success"}),
    }


def format_response_node(state: AfterSalesAgentState) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    state_with_trace = {
        **state,
        "tool_trace": _append_trace(state, {"step": "format_response", "status": "success"}),
    }
    return {
        "formatted_response": format_agent_response(state_with_trace),
        "tool_trace": state_with_trace["tool_trace"],
    }


def _tool_error_update(
    state: AfterSalesAgentState,
    tool_name: str,
    error: Exception,
    trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    tool_trace = trace or {"step": tool_name, "status": "error"}
    tool_trace = {**tool_trace, "error": str(error)}
    return {
        "tool_used": tool_name,
        "answer_status": "tool_error",
        "answer": "工具调用失败，当前无法完成请求，请稍后重试或转人工处理。",
        "error": str(error),
        "needs_human_review": True,
        "confirmation_required": False,
        "tool_trace": _append_trace(
            state,
            tool_trace,
        ),
    }


def build_after_sales_graph():
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    graph_builder = StateGraph(AfterSalesAgentState)

    graph_builder.add_node("receive_request_node", receive_request_node)
    graph_builder.add_node("extract_entities_node", extract_entities_node)
    graph_builder.add_node("classify_intent_node", classify_intent_node)
    graph_builder.add_node("ask_for_order_id_node", ask_for_order_id_node)
    graph_builder.add_node("policy_qa_node", policy_qa_node)
    graph_builder.add_node("order_lookup_node", order_lookup_node)
    graph_builder.add_node("refund_eligibility_node", refund_eligibility_node)
    graph_builder.add_node("refund_then_ticket_workflow_node", refund_then_ticket_workflow_node)
    graph_builder.add_node("ticket_confirmation_node", ticket_confirmation_node)
    graph_builder.add_node("create_ticket_node", create_ticket_node)
    graph_builder.add_node("human_handoff_node", human_handoff_node)
    graph_builder.add_node("unknown_node", unknown_node)
    graph_builder.add_node("format_response_node", format_response_node)

    graph_builder.add_edge(START, "receive_request_node")
    graph_builder.add_edge("receive_request_node", "extract_entities_node")
    graph_builder.add_edge("extract_entities_node", "classify_intent_node")
    graph_builder.add_conditional_edges(
        "classify_intent_node",
        route_after_classification,
        {
            "policy_qa": "policy_qa_node",
            "order_lookup": "order_lookup_node",
            "refund_eligibility": "refund_eligibility_node",
            CONTROLLED_WORKFLOW_REFUND_THEN_TICKET: "refund_then_ticket_workflow_node",
            "ask_for_order_id": "ask_for_order_id_node",
            "ticket_confirmation": "ticket_confirmation_node",
            "create_ticket": "create_ticket_node",
            "human_handoff": "human_handoff_node",
            "unknown": "unknown_node",
        },
    )

    for node_name in [
        "ask_for_order_id_node",
        "policy_qa_node",
        "order_lookup_node",
        "refund_eligibility_node",
        "refund_then_ticket_workflow_node",
        "ticket_confirmation_node",
        "create_ticket_node",
        "human_handoff_node",
        "unknown_node",
    ]:
        graph_builder.add_edge(node_name, "format_response_node")

    graph_builder.add_edge("format_response_node", END)
    return graph_builder.compile()

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
