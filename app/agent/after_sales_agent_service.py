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
from uuid import uuid4

from app.agent.after_sales_graph import build_after_sales_graph
from app.agent.response_formatter import format_agent_response
from app.tools.policy_qa_tool import ask_policy_question


def run_after_sales_agent(
    user_query: str,
    confirm_ticket_creation: bool = False,
    request_id: str | None = None,
    policy_qa_callable: Callable[..., dict[str, Any]] | None = None,
) -> dict:
    """
    构建并执行 LangGraph，返回统一 JSON 可序列化 dict。
    """
    actual_request_id = request_id or str(uuid4())
    cleaned_query = (user_query or "").strip()

    if not cleaned_query:
        return format_agent_response(
            {
                "request_id": actual_request_id,
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

    graph = build_after_sales_graph()
    initial_state = {
        "request_id": actual_request_id,
        "user_query": cleaned_query,
        "confirm_ticket_creation": confirm_ticket_creation,
        "policy_qa_callable": policy_qa_callable or ask_policy_question,
        "tool_trace": [],
        "citations": [],
        "debug": {},
        "error": None,
    }
    final_state = graph.invoke(initial_state)
    return final_state.get("formatted_response") or format_agent_response(final_state)

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
