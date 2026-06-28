"""Typed state passed between after-sales Agent graph nodes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict


class AfterSalesAgentState(TypedDict, total=False):
    """One request state. It is not long-term memory."""

    request_id: str
    session_id: str
    user_query: str
    confirm_ticket_creation: bool
    idempotency_key: str | None
    policy_qa_callable: Callable[..., dict[str, Any]]

    order_id: str | None
    all_detected_order_ids: list[str]

    intent: str
    intent_reason: str
    requires_order_id: bool

    tool_used: str | None
    tool_trace: list[dict[str, Any]]

    policy_qa_result: dict[str, Any] | None
    order_result: dict[str, Any] | None
    refund_result: dict[str, Any] | None
    ticket_result: dict[str, Any] | None

    answer_status: str
    answer: str
    citations: list[dict[str, Any]]
    needs_human_review: bool
    confirmation_required: bool

    # Retry/degradation fields are explicit so LangGraph keeps them in state.
    error_category: str | None
    retry_count: int
    degraded: bool
    fallback_action: str | None

    # Controlled workflow orchestration fields. These are request-scoped only.
    workflow_type: str | None
    task_plan: list[str]
    current_step: str | None
    plan_status: str | None
    fallback_requested: bool
    next_action: str | None
    max_steps: int
    executed_steps: list[str]
    workflow_summary: dict[str, Any] | None
    data: dict[str, Any]

    error: str | None
    debug: dict[str, Any]
    formatted_response: dict[str, Any]
