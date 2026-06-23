"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


AnswerStatus = Literal[
    "answered",
    "missing_order_id",
    "ticket_confirmation_required",
    "manual_review",
    "unknown_request",
    "tool_error",
]


class AfterSalesAgentResponse(BaseModel):
    success: bool = Field(description="本次 Agent 流程是否成功完成。")
    request_id: str = Field(description="请求编号。")
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
    tool_trace: list[dict[str, Any]] = Field(description="节点和工具调用轨迹。")
    tool_latency_summary: dict[str, Any] = Field(description="Tool 调用耗时汇总。")
    error: str | None = Field(description="错误信息。")
    debug: dict[str, Any] = Field(description="调试信息。")
