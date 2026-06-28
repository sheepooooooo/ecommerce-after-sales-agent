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


from typing import Any

from app.schemas.after_sales_agent_schema import AfterSalesAgentResponse
from app.observability.trace_utils import summarize_tool_latency
from app.services.error_taxonomy import business_error_category_from_response


PAYMENT_STATUS_TEXT = {
    "unpaid": "待付款",
    "paid": "已付款",
}

SHIPPING_STATUS_TEXT = {
    "unshipped": "未发货",
    "shipped": "已发货未签收",
    "delivered": "已签收",
}

REFUND_STATUS_TEXT = {
    "none": "暂无退款",
    "refunded": "已退款",
    "cancelled": "已取消",
}


def _dump_model_if_needed(item: Any) -> Any:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if isinstance(item, list):
        return [_dump_model_if_needed(value) for value in item]
    if isinstance(item, dict):
        return {key: _dump_model_if_needed(value) for key, value in item.items()}
    return item


def _build_order_data(order: dict[str, Any] | None) -> dict[str, Any]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    if not order:
        return {}
    return {
        "order_id": order.get("order_id"),
        "product_name": order.get("product_name"),
        "payment_status": order.get("payment_status"),
        "payment_status_text": PAYMENT_STATUS_TEXT.get(order.get("payment_status"), "未知支付状态"),
        "shipping_status": order.get("shipping_status"),
        "shipping_status_text": SHIPPING_STATUS_TEXT.get(order.get("shipping_status"), "未知物流状态"),
        "refund_status": order.get("refund_status"),
        "refund_status_text": REFUND_STATUS_TEXT.get(order.get("refund_status"), "未知退款状态"),
    }


def _format_order_answer(order: dict[str, Any] | None, order_id: str | None) -> tuple[str, dict[str, Any], bool]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    if not order:
        return f"未查询到订单 {order_id}，请核对订单号后重试。", {"order_id": order_id}, True

    data = _build_order_data(order)
    answer = (
        f"订单 {data['order_id']} 的商品是 {data['product_name']}。"
        f"支付状态：{data['payment_status_text']}；"
        f"物流状态：{data['shipping_status_text']}；"
        f"退款状态：{data['refund_status_text']}。"
    )
    return answer, data, False


def _format_refund_answer(refund_result: dict[str, Any] | None) -> tuple[str, dict[str, Any], bool, str]:
    """
    本函数是当前模块的辅助或核心步骤。
    
    参数：
        见函数签名。
    
    返回：
        见调用方使用的结构化结果。
    
    副作用：
        不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
    """
    if not refund_result:
        return "退款资格判断没有返回结果，请稍后重试。", {}, True, "manual_review"

    data = {
        "order_id": refund_result.get("order_id"),
        "decision": refund_result.get("decision"),
        "eligible": refund_result.get("eligible"),
        "refund_type": refund_result.get("refund_type"),
        "reason": refund_result.get("reason"),
        "next_action": refund_result.get("next_action"),
        "days_since_delivery": refund_result.get("days_since_delivery"),
    }
    decision = refund_result.get("decision")
    if decision == "eligible":
        prefix = "该订单当前规则判断为可退款。"
        needs_human_review = False
        answer_status = "answered"
    elif decision == "not_eligible":
        prefix = "该订单当前规则判断为不可直接退款。"
        needs_human_review = False
        answer_status = "answered"
    else:
        prefix = "该订单需要人工进一步处理。"
        needs_human_review = True
        answer_status = "manual_review"

    answer = (
        f"{prefix}原因：{refund_result.get('reason')} "
        f"下一步建议：{refund_result.get('next_action')} "
        "该结论来自订单事实与退款规则引擎，不是模型猜测。"
    )
    return answer, data, needs_human_review, answer_status


def format_agent_response(state: dict[str, Any]) -> dict[str, Any]:
    """
    把图执行 state 转成 JSON 可序列化的统一响应。
    """
    answer_status = state.get("answer_status") or "unknown_request"
    intent = state.get("intent") or "unknown"
    data: dict[str, Any] = {}
    answer = state.get("answer") or ""
    needs_human_review = bool(state.get("needs_human_review", False))

    if answer_status == "missing_order_id":
        data = {"required_format": "ORD10003"}
    elif answer_status == "ticket_confirmation_required":
        data = _dump_model_if_needed(state.get("data")) if state.get("data") else {
            "order_id": state.get("order_id"),
            "confirm_ticket_creation": False,
        }
    elif intent == "policy_qa" and state.get("policy_qa_result"):
        policy_result = state["policy_qa_result"]
        answer = answer or policy_result.get("answer", "")
        data = {
            "policy_qa": {
                "answer_status": policy_result.get("answer_status"),
                "has_relevant_policy": policy_result.get("has_relevant_policy"),
                "grounding_verification": _dump_model_if_needed(policy_result.get("grounding_verification")),
            }
        }
        needs_human_review = bool(policy_result.get("answer_status") == "manual_review")
    elif intent == "order_lookup":
        answer, data, needs_human_review = _format_order_answer(
            state.get("order_result"),
            state.get("order_id"),
        )
    elif intent == "refund_eligibility":
        answer, data, needs_human_review, answer_status = _format_refund_answer(state.get("refund_result"))
    elif intent == "refund_then_ticket_if_ineligible":
        data = _dump_model_if_needed(state.get("data", {}))
        answer = answer or "复合售后流程已执行。"
        needs_human_review = bool(state.get("needs_human_review", False))
    elif intent == "create_ticket" and state.get("ticket_result"):
        ticket = state["ticket_result"]
        data = {"ticket": ticket}
        answer = (
            f"已创建模拟售后工单，工单编号为 {ticket.get('ticket_id')}。"
            "当前仅写入本地模拟数据库，不代表真实客服系统已受理。"
        )
    elif state.get("data"):
        data = _dump_model_if_needed(state.get("data"))
    success = answer_status not in {"tool_error"}
    debug = _dump_model_if_needed(state.get("debug", {}))
    provisional = {
        "answer_status": answer_status,
        "intent": intent,
        "tool_used": state.get("tool_used"),
        "answer": answer,
        "debug": debug,
    }
    response = AfterSalesAgentResponse(
        success=success,
        request_id=state.get("request_id", ""),
        session_id=state.get("session_id", ""),
        user_query=state.get("user_query", ""),
        intent=intent,
        intent_reason=state.get("intent_reason", ""),
        tool_used=state.get("tool_used"),
        answer_status=answer_status,
        answer=answer,
        data=_dump_model_if_needed(data),
        citations=_dump_model_if_needed(state.get("citations", [])),
        needs_human_review=needs_human_review,
        confirmation_required=bool(state.get("confirmation_required", False)),
        tool_trace=_dump_model_if_needed(state.get("tool_trace", [])),
        tool_latency_summary=summarize_tool_latency(state.get("tool_trace", [])),
        error=state.get("error"),
        error_category=state.get("error_category") or business_error_category_from_response(provisional),
        retry_count=int(state.get("retry_count") or debug.get("retry_count") or 0),
        degraded=bool(state.get("degraded", False)),
        fallback_action=state.get("fallback_action"),
        workflow_summary=_dump_model_if_needed(
            state.get("workflow_summary")
            or data.get("workflow_summary")
            if isinstance(data, dict)
            else None
        ),
        debug=debug,
    )
    return response.model_dump()

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
