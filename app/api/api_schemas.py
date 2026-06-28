"""Pydantic schemas for the FastAPI layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class AgentRunRequest(BaseModel):
    """/agent/run request body."""

    model_config = ConfigDict(extra="forbid")

    user_query: str = Field(description="用户售后问题，去除首尾空格后长度为 1 到 1000。")
    confirm_ticket_creation: StrictBool = Field(
        default=False,
        description="是否显式确认创建本地模拟售后工单。",
    )
    request_id: str | None = Field(
        default=None,
        max_length=100,
        description="可选请求编号；未传时由服务端生成 UUID。",
    )
    session_id: str | None = Field(
        default=None,
        max_length=100,
        description="可选会话编号；未传时由服务端生成，用于恢复多轮确认状态。",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=120,
        description="可选幂等键；重复提交同一写操作时返回同一模拟工单结果。",
    )

    @field_validator("user_query")
    @classmethod
    def validate_user_query(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("user_query 必须是字符串。")
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("user_query 不能为空。")
        if len(cleaned_value) > 1000:
            raise ValueError("user_query 长度不能超过 1000。")
        return cleaned_value

    @field_validator("request_id", "session_id", "idempotency_key")
    @classmethod
    def validate_optional_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned_value = value.strip()
        return cleaned_value or None


class ApiErrorDetail(BaseModel):
    """API error detail."""

    loc: list[Any] = Field(default_factory=list, description="错误字段位置。")
    message: str = Field(description="可读错误说明。")
    type: str | None = Field(default=None, description="错误类型。")


class ApiErrorResponse(BaseModel):
    """Unified API error response."""

    success: bool = Field(default=False, description="固定为 false，表示请求失败。")
    request_id: str = Field(description="请求编号。")
    error: dict[str, Any] = Field(description="错误 code、message 和 details。")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(description="服务状态。")
    service: str = Field(description="服务名称。")
    version: str = Field(description="服务版本。")


class AgentRunResponse(BaseModel):
    """/agent/run response schema."""

    success: bool = Field(description="Agent 是否成功完成。")
    request_id: str = Field(description="请求编号。")
    session_id: str = Field(description="会话编号，用于多轮确认状态恢复。")
    user_query: str = Field(description="用户原始问题。")
    intent: str = Field(description="识别到的意图。")
    intent_reason: str = Field(description="意图分类原因。")
    tool_used: str | None = Field(description="实际调用的 Tool。")
    answer_status: str = Field(description="统一回答状态。")
    answer: str = Field(description="面向用户的中文回答。")
    data: dict[str, Any] = Field(description="结构化业务数据。")
    citations: list[dict[str, Any]] = Field(description="政策引用。")
    needs_human_review: bool = Field(description="是否建议人工处理。")
    confirmation_required: bool = Field(description="是否需要确认。")
    tool_trace: list[dict[str, Any]] = Field(description="节点和 Tool 调用摘要。")
    tool_latency_summary: dict[str, Any] = Field(description="Tool 耗时汇总。")
    error: str | None = Field(description="Agent 错误信息。")
    error_category: str | None = Field(default=None, description="统一错误分类。")
    retry_count: int = Field(default=0, description="只读外部调用累计重试次数。")
    degraded: bool = Field(default=False, description="是否进入安全降级。")
    fallback_action: str | None = Field(default=None, description="降级时采取的兜底动作。")
    workflow_summary: dict[str, Any] | None = Field(default=None, description="受控复合工作流的步骤摘要；非复合请求为 None。")
    debug: dict[str, Any] = Field(description="调试信息，不包含密钥或完整 Prompt。")
    api_latency_ms: float = Field(description="API 总耗时，毫秒。")
    agent_latency_ms: float = Field(description="Agent 执行耗时，毫秒。")
    api_version: str = Field(description="API 版本。")


class TraceEventResponse(BaseModel):
    """One sanitized persisted trace event."""

    request_id: str
    session_id: str
    step_index: int
    node_name: str
    action_type: str
    tool_name: str | None
    parameter_summary: str
    result_summary: str
    status: str
    latency_ms: float
    error_category: str | None
    retry_count: int
    created_at: str


class AgentTraceResponse(BaseModel):
    """Read-only trace query response."""

    request_id: str
    event_count: int
    events: list[TraceEventResponse]
