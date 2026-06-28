"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from typing import Any

import app.agent.after_sales_graph as after_sales_graph
from app.agent.after_sales_agent_service import run_after_sales_agent
from scripts.init_demo_data import initialize_database


def policy_stub(query: str) -> dict[str, Any]:
    return {
        "success": True,
        "query": query,
        "answer_status": "answered",
        "answer": "stub",
        "retrieval_mode": "stub",
        "retrieved_chunks": [],
        "citations": [],
        "has_relevant_policy": True,
        "generation": None,
        "grounding_verification": {"passed": True},
        "message": "ok",
        "error": None,
        "debug": {"llm_called": False},
    }


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_graph_order_lookup_path() -> None:
    initialize_database()

    result = run_after_sales_agent("ORD10003 的物流怎么样", policy_qa_callable=policy_stub)

    assert result["intent"] == "order_lookup"
    assert result["tool_used"] == "order_tool.get_order"
    assert result["data"]["order_id"] == "ORD10003"
    assert result["answer_status"] == "answered"


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_graph_multiple_order_ids_keeps_all_debug_values() -> None:
    initialize_database()

    result = run_after_sales_agent("比较 ORD10003 和 ORD10004 的状态", policy_qa_callable=policy_stub)

    assert result["data"]["order_id"] == "ORD10003"
    assert result["debug"]["all_detected_order_ids"] == ["ORD10003", "ORD10004"]


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_graph_tool_exception_returns_tool_error(monkeypatch: Any) -> None:
    initialize_database()

    def broken_get_order(order_id: str) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(after_sales_graph, "get_order", broken_get_order)

    result = run_after_sales_agent("ORD10003 的物流怎么样", policy_qa_callable=policy_stub)

    assert result["answer_status"] == "tool_error"
    assert result["success"] is False
    assert result["error"] == "boom"


def test_create_ticket_failure_is_not_retried(monkeypatch: Any) -> None:
    initialize_database()
    state = {"count": 0}

    def broken_create_ticket(*args: Any, **kwargs: Any) -> dict[str, Any]:
        state["count"] += 1
        raise RuntimeError("write failed")

    monkeypatch.setattr(after_sales_graph, "create_ticket", broken_create_ticket)

    result = run_after_sales_agent(
        "请帮我创建工单，订单号 ORD10003",
        confirm_ticket_creation=True,
        policy_qa_callable=policy_stub,
    )

    assert result["answer_status"] == "tool_error"
    assert result["success"] is False
    assert state["count"] == 1
