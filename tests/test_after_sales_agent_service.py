"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

from typing import Any

from app.agent.after_sales_agent_service import run_after_sales_agent
from app.tools.order_tool import list_tickets
from scripts.init_demo_data import initialize_database


def policy_stub(query: str) -> dict[str, Any]:
    return {
        "success": True,
        "query": query,
        "answer_status": "answered",
        "answer": "stub policy answer",
        "retrieval_mode": "stub",
        "retrieved_chunks": [],
        "citations": [{"chunk_id": "stub", "source_file": "stub.md", "section_title": "stub"}],
        "has_relevant_policy": True,
        "generation": None,
        "grounding_verification": {"passed": True},
        "message": "ok",
        "error": None,
        "debug": {"llm_called": False},
    }


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_missing_order_id_does_not_call_refund_tool() -> None:
    initialize_database()

    result = run_after_sales_agent("我想退款", policy_qa_callable=policy_stub)

    assert result["intent"] == "refund_eligibility"
    assert result["answer_status"] == "missing_order_id"
    assert result["tool_used"] is None
    assert "refund_eligibility_tool.check_refund_eligibility" not in [
        trace["step"] for trace in result["tool_trace"]
    ]


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_policy_qa_uses_stub() -> None:
    initialize_database()

    result = run_after_sales_agent("耳机保修多久", policy_qa_callable=policy_stub)

    assert result["intent"] == "policy_qa"
    assert result["tool_used"] == "policy_qa_tool.ask_policy_question"
    assert result["answer"] == "stub policy answer"
    assert result["debug"]["policy_qa"]["llm_called"] is False


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_ticket_not_created_without_confirmation() -> None:
    initialize_database()

    result = run_after_sales_agent("请帮我创建工单，订单号 ORD10003")

    assert result["answer_status"] == "ticket_confirmation_required"
    assert result["tool_used"] is None
    assert list_tickets("ORD10003") == []


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_ticket_created_only_when_confirmed() -> None:
    initialize_database()

    result = run_after_sales_agent(
        "请帮我创建工单，订单号 ORD10003",
        confirm_ticket_creation=True,
    )

    assert result["answer_status"] == "answered"
    assert result["tool_used"] == "order_tool.create_ticket"
    tickets = list_tickets("ORD10003")
    assert len(tickets) == 1
    assert tickets[0]["ticket_id"] == result["data"]["ticket"]["ticket_id"]


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_human_handoff_and_unknown() -> None:
    initialize_database()

    handoff = run_after_sales_agent("支付异常，我的银行卡被重复扣款了")
    unknown = run_after_sales_agent("今天天气怎么样")

    assert handoff["intent"] == "human_handoff"
    assert handoff["answer_status"] == "manual_review"
    assert handoff["tool_used"] is None
    assert unknown["intent"] == "unknown"
    assert unknown["answer_status"] == "unknown_request"
