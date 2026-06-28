"""After-sales Agent response schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AnswerStatus = Literal[
    "answered",
    "missing_order_id",
    "ticket_confirmation_required",
    "manual_review",
    "unknown_request",
    "tool_error",
    "degraded",
]


class AfterSalesAgentResponse(BaseModel):
    success: bool = Field(description="本次 Agent 流程是否成功完成。")
    request_id: str = Field(description="请求编号。")
    session_id: str = Field(description="会话编号，用于多轮确认状态恢复。")
    user_query: str = Field(description="用户原始问题。")
    intent: str = Field(description="识别到的意图。")
    intent_reason: str = Field(description="意图分类原因。")
    tool_used: str | None = Field(description="实际调用的 Tool 名称。")
    answer_status: AnswerStatus = Field(description="统一回答状态。")
    answer: str = Field(description="面向用户的中文回答。")
    data: dict[str, Any] = Field(description="结构化业务结果。")
    citations: list[dict[str, Any]] = Field(description="政策引用列表。")
    needs_human_review: bool = Field(description="是否需要人工处理。")
    confirmation_required: bool = Field(description="是否需要用户确认。")
    tool_trace: list[dict[str, Any]] = Field(description="节点和工具调用轨迹摘要。")
    tool_latency_summary: dict[str, Any] = Field(description="Tool 调用耗时汇总。")
    error: str | None = Field(description="错误信息；无错误时为 None。")
    error_category: str | None = Field(default=None, description="统一错误分类。")
    retry_count: int = Field(default=0, description="只读外部调用累计重试次数。")
    degraded: bool = Field(default=False, description="是否进入安全降级。")
    fallback_action: str | None = Field(default=None, description="降级时采取的兜底动作。")
    workflow_summary: dict[str, Any] | None = Field(default=None, description="受控复合工作流的步骤摘要；非复合请求为 None。")
    debug: dict[str, Any] = Field(description="调试信息，不包含 API Key、敏感信息或完整 Prompt。")
