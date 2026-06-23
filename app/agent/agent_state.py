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


from typing import Any, Callable, TypedDict


class AfterSalesAgentState(TypedDict, total=False):
    """一次售后 Agent 请求在各节点之间传递的状态，不是长期 Memory。"""

    request_id: str  # 本次请求编号，用于串联一次图执行。
    user_query: str  # 用户原始问题，不保存密码、验证码等敏感扩展信息。
    confirm_ticket_creation: bool  # 是否已显式确认创建模拟工单。
    policy_qa_callable: Callable[..., dict[str, Any]]  # 可注入的政策问答函数，测试中用 stub。

    order_id: str | None  # 从用户问题中提取的第一个标准化订单号。
    all_detected_order_ids: list[str]  # 当前问题中全部匹配到的订单号，用于 debug。

    intent: str  # 规则分类得到的意图。
    intent_reason: str  # 意图分类原因，便于调试和面试解释。
    requires_order_id: bool  # 当前意图是否需要订单号才能继续。

    tool_used: str | None  # 最终调用的业务 Tool 名称；未调用时为 None。
    tool_trace: list[dict[str, Any]]  # 节点和 Tool 调用轨迹，不保存 API Key 或完整系统 Prompt。

    policy_qa_result: dict[str, Any] | None  # 政策问答 Tool 返回。
    order_result: dict[str, Any] | None  # 订单查询 Tool 返回。
    refund_result: dict[str, Any] | None  # 退款资格 Tool 返回。
    ticket_result: dict[str, Any] | None  # 工单创建 Tool 返回。

    answer_status: str  # 统一回答状态，例如 answered、missing_order_id、tool_error。
    answer: str  # 面向用户的中文回答。
    citations: list[dict[str, Any]]  # 政策引用列表，仅政策问答路径通常有值。
    needs_human_review: bool  # 是否建议人工处理。
    confirmation_required: bool  # 是否需要用户确认后才能继续写入工单。

    error: str | None  # 统一错误信息；无错误时为 None。
    debug: dict[str, Any]  # 调试信息，不保存 API Key、敏感信息或完整 LLM Prompt。

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
