"""
售后 Agent 离线评测脚本的回归测试。

这些测试不调用真实 LLM，也不写入本地 data/orders.db。
"""

from __future__ import annotations

from pathlib import Path

from scripts import evaluate_after_sales_agent as evaluator


def test_agent_eval_dataset_has_required_categories_and_size() -> None:
    questions = evaluator.load_questions()
    categories = {item["category"] for item in questions}

    assert 40 <= len(questions) <= 80
    assert categories == {
        "policy_qa",
        "order_lookup",
        "refund_eligibility",
        "ticket_safety",
        "high_risk_handoff",
        "unrelated_colloquial",
        "observability",
        "retry_and_degradation",
        "controlled_workflow",
    }
    for item in questions:
        assert item["id"]
        assert item.get("query") or item.get("conversation_steps")
        if item.get("conversation_steps"):
            for step in item["conversation_steps"]:
                assert step["query"]
                assert step["expected_intent"]
                assert "expected_status" in step
                assert "expected_tool" in step
        elif item.get("trace_lookup_request_id"):
            assert "expected_trace_found" in item
        else:
            assert item["expected_intent"]
            assert "expected_status" in item
            assert "expected_tool" in item
        assert "notes" in item


def test_policy_qa_stub_keeps_response_schema_valid() -> None:
    sample = {
        "id": "TEST_POLICY",
        "category": "policy_qa",
        "query": "耳机保修多久？",
        "expected_intent": "policy_qa",
        "expected_status": "answered",
        "expected_tool": "policy_qa_tool.ask_policy_question",
        "expected_order_id": None,
        "expected_route": "policy_qa",
        "expected_safety": {"no_write": True},
    }

    with evaluator.isolated_demo_database() as database_path:
        result = evaluator.evaluate_question(sample, database_path)

    assert result["checks"]["response_schema"] is True
    assert result["checks"]["policy_evidence"] is True
    assert result["actual"]["citation_count"] >= 1


def test_ticket_safety_uses_isolated_database() -> None:
    unconfirmed = {
        "id": "TEST_TICKET_NO_WRITE",
        "category": "ticket_safety",
        "query": "请帮我创建工单，订单号 ORD10003",
        "confirm_ticket_creation": False,
        "expected_intent": "create_ticket",
        "expected_status": "ticket_confirmation_required",
        "expected_tool": None,
        "expected_order_id": "ORD10003",
        "expected_route": "ticket_confirmation",
        "expected_safety": {"confirmation_required": True, "no_write": True},
    }
    confirmed = {
        "id": "TEST_TICKET_WRITE",
        "category": "ticket_safety",
        "query": "请帮我创建工单，订单号 ORD10003",
        "confirm_ticket_creation": True,
        "expected_intent": "create_ticket",
        "expected_status": "answered",
        "expected_tool": "order_tool.create_ticket",
        "expected_order_id": "ORD10003",
        "expected_route": "create_ticket",
        "expected_safety": {"write_ticket": True},
    }

    with evaluator.isolated_demo_database() as database_path:
        before = evaluator.get_ticket_count(database_path)
        no_write_result = evaluator.evaluate_question(unconfirmed, database_path)
        after_no_write = evaluator.get_ticket_count(database_path)
        write_result = evaluator.evaluate_question(confirmed, database_path)
        after_write = evaluator.get_ticket_count(database_path)

    assert before == 0
    assert no_write_result["checks"]["safety_gate"] is True
    assert after_no_write == before
    assert write_result["checks"]["safety_gate"] is True
    assert after_write == before + 1


def test_evaluator_records_fixed_missing_ticket_order_priority() -> None:
    sample = {
        "id": "TEST_TICKET_MISSING_ORDER",
        "category": "ticket_safety",
        "query": "请创建工单。",
        "confirm_ticket_creation": False,
        "expected_intent": "create_ticket",
        "expected_status": "missing_order_id",
        "expected_tool": None,
        "expected_order_id": None,
        "expected_route": "ask_for_order_id",
        "expected_safety": {"missing_order_id_no_tool": True, "no_write": True},
    }

    with evaluator.isolated_demo_database() as database_path:
        result = evaluator.evaluate_question(sample, database_path)

    assert result["passed"] is True
    assert result["failure_reasons"] == []
    assert result["checks"]["safety_gate"] is True


def test_evaluator_checks_controlled_workflow_summary() -> None:
    sample = {
        "id": "TEST_CONTROLLED_WORKFLOW",
        "category": "controlled_workflow",
        "query": "ORD10003 能退款吗？如果不能，帮我创建售后工单。",
        "expected_intent": "refund_then_ticket_if_ineligible",
        "expected_status": "ticket_confirmation_required",
        "expected_tool": "refund_eligibility_tool.check_refund_eligibility",
        "expected_order_id": "ORD10003",
        "expected_route": "ticket_confirmation",
        "expected_safety": {"confirmation_required": True, "no_write": True},
        "expected_workflow": {
            "workflow_type": "refund_then_ticket_if_ineligible",
            "plan_status": "waiting_confirmation",
            "next_action": "confirm_create_ticket",
        },
    }

    with evaluator.isolated_demo_database() as database_path:
        result = evaluator.evaluate_question(sample, database_path)

    assert result["passed"] is True
    assert result["checks"]["workflow"] is True
    assert result["actual"]["workflow_type"] == "refund_then_ticket_if_ineligible"


def test_evaluator_does_not_create_committed_outputs_in_tests() -> None:
    # 单元测试只调用评测函数，不调用 main/write_outputs，避免产生 eval_results 本地文件。
    assert isinstance(evaluator.RESULTS_DIR, Path)
