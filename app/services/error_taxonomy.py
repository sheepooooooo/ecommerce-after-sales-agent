"""Unified error categories used by responses, traces and evaluation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    MISSING_ORDER_ID = "missing_order_id"
    ORDER_NOT_FOUND = "order_not_found"
    REFUND_NOT_ELIGIBLE = "refund_not_eligible"
    TICKET_CONFIRMATION_REQUIRED = "ticket_confirmation_required"
    NO_PENDING_ACTION = "no_pending_action"
    USER_CANCELLED = "user_cancelled"
    HUMAN_HANDOFF = "human_handoff"
    UNKNOWN_REQUEST = "unknown_request"
    VALIDATION_ERROR = "validation_error"
    LLM_TIMEOUT = "llm_timeout"
    LLM_NETWORK_ERROR = "llm_network_error"
    LLM_RATE_LIMIT = "llm_rate_limit"
    RETRYABLE_RETRIEVAL_ERROR = "retryable_retrieval_error"
    LLM_CONFIGURATION_ERROR = "llm_configuration_error"
    INVALID_REQUEST = "invalid_request"
    NON_RETRYABLE_SCHEMA_ERROR = "non_retryable_schema_error"
    INTERNAL_ERROR = "internal_error"


RETRYABLE_ERROR_CATEGORIES = {
    ErrorCategory.LLM_TIMEOUT.value,
    ErrorCategory.LLM_NETWORK_ERROR.value,
    ErrorCategory.LLM_RATE_LIMIT.value,
    ErrorCategory.RETRYABLE_RETRIEVAL_ERROR.value,
}


def classify_exception(error: Exception) -> str:
    """Map exceptions to stable, non-secret error categories."""
    explicit_category = getattr(error, "error_category", None)
    if explicit_category:
        return str(explicit_category)

    error_type = type(error).__name__.lower()
    error_text = str(error).lower()
    if "timeout" in error_type or "timeout" in error_text or "超时" in error_text:
        return ErrorCategory.LLM_TIMEOUT.value
    if "rate" in error_text or "429" in error_text or "限流" in error_text:
        return ErrorCategory.LLM_RATE_LIMIT.value
    if "connection" in error_type or "network" in error_text or "网络" in error_text:
        return ErrorCategory.LLM_NETWORK_ERROR.value
    if "api key" in error_text or "apikey" in error_text or "未检测到 deepseek_api_key" in error_text:
        return ErrorCategory.LLM_CONFIGURATION_ERROR.value
    if "json" in error_text or "schema" in error_text or "validation" in error_type:
        return ErrorCategory.NON_RETRYABLE_SCHEMA_ERROR.value
    if isinstance(error, (ValueError, TypeError)):
        return ErrorCategory.INVALID_REQUEST.value
    return ErrorCategory.INTERNAL_ERROR.value


def is_retryable_category(category: str | None) -> bool:
    return bool(category and category in RETRYABLE_ERROR_CATEGORIES)


def business_error_category_from_response(response: dict[str, Any]) -> str | None:
    """Classify normal business outcomes without treating them as exceptions."""
    status = response.get("answer_status")
    intent = response.get("intent")
    if status == "missing_order_id":
        return ErrorCategory.MISSING_ORDER_ID.value
    if status == "ticket_confirmation_required":
        return ErrorCategory.TICKET_CONFIRMATION_REQUIRED.value
    if status == "unknown_request":
        return ErrorCategory.UNKNOWN_REQUEST.value
    if status == "manual_review" and intent == "human_handoff":
        return ErrorCategory.HUMAN_HANDOFF.value
    if status == "manual_review" and response.get("tool_used") == "order_tool.get_order":
        return ErrorCategory.ORDER_NOT_FOUND.value
    if intent == "session_control" and response.get("tool_used") is None:
        text = str(response.get("answer", ""))
        if "取消" in text:
            return ErrorCategory.USER_CANCELLED.value
        if "没有待确认" in text:
            return ErrorCategory.NO_PENDING_ACTION.value
    return response.get("debug", {}).get("error_category")
