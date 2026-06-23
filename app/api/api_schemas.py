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

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class AgentRunRequest(BaseModel):
    """
    /agent/run 请求体。
    """

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

    @field_validator("user_query")
    @classmethod
    def validate_user_query(cls, value: str) -> str:
        """
        本函数是当前模块的辅助或核心步骤。
        
        参数：
            见函数签名。
        
        返回：
            见调用方使用的结构化结果。
        
        副作用：
            不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
        """
        if not isinstance(value, str):
            raise TypeError("user_query 必须是字符串。")
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("user_query 不能为空。")
        if len(cleaned_value) > 1000:
            raise ValueError("user_query 长度不能超过 1000。")
        return cleaned_value

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str | None) -> str | None:
        """
        本函数是当前模块的辅助或核心步骤。
        
        参数：
            见函数签名。
        
        返回：
            见调用方使用的结构化结果。
        
        副作用：
            不新增业务能力。是否读写数据库或调用 LLM，以本函数已有代码和上层调用链为准。
        """
        if value is None:
            return None
        cleaned_value = value.strip()
        if not cleaned_value:
            return None
        if len(cleaned_value) > 100:
            raise ValueError("request_id 长度不能超过 100。")
        return cleaned_value


class ApiErrorDetail(BaseModel):
    """
    API 错误详情。
    """

    loc: list[Any] = Field(default_factory=list, description="错误字段位置。")
    message: str = Field(description="可读错误说明。")
    type: str | None = Field(default=None, description="错误类型。")


class ApiErrorResponse(BaseModel):
    """
    API 统一错误响应。
    """

    success: bool = Field(default=False, description="固定为 false，表示请求失败。")
    request_id: str = Field(description="请求编号。")
    error: dict[str, Any] = Field(description="错误 code、message 和 details。")


class HealthResponse(BaseModel):
    """
    健康检查响应。
    """

    status: str = Field(description="服务状态。")
    service: str = Field(description="服务名称。")
    version: str = Field(description="服务版本。")


class AgentRunResponse(BaseModel):
    """
    /agent/run 响应约束。
    """

    success: bool = Field(description="Agent 是否成功完成。")
    request_id: str = Field(description="请求编号。")
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
    tool_trace: list[dict[str, Any]] = Field(description="节点和 Tool 调用轨迹。")
    tool_latency_summary: dict[str, Any] = Field(description="Tool 耗时汇总。")
    error: str | None = Field(description="Agent 错误信息。")
    debug: dict[str, Any] = Field(description="调试信息。")
    api_latency_ms: float = Field(description="API 总耗时，毫秒。")
    agent_latency_ms: float = Field(description="Agent 执行耗时，毫秒。")
    api_version: str = Field(description="API 版本。")

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
