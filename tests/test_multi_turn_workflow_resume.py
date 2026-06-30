"""Regression tests for missing-information task resume.

These tests use the evaluator's isolated SQLite database, so they do not write
to the local demo database under data/orders.db.
"""

from __future__ import annotations

from app.agent.after_sales_agent_service import run_after_sales_agent
from app.services.session_store import (
    SESSION_STATUS_AWAITING_ORDER_ID,
    SESSION_STATUS_CANCELLED,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_IDLE,
    SESSION_STATUS_INTERRUPTED,
    SESSION_STATUS_PENDING,
    get_session,
)
from app.services.trace_store import list_trace_events
from app.tools.order_tool import list_tickets
from scripts.evaluate_after_sales_agent import isolated_demo_database, policy_qa_stub


def test_refund_missing_order_id_then_resume_refund_check() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("帮我退款", request_id="resume-refund-1")
        session = get_session(first["session_id"])

        assert first["answer_status"] == "missing_order_id"
        assert first["tool_used"] is None
        assert session["conversation_status"] == SESSION_STATUS_AWAITING_ORDER_ID
        assert session["pending_action"] == "refund_eligibility"

        second = run_after_sales_agent("ORD10003", session_id=first["session_id"], request_id="resume-refund-2")
        assert second["intent"] == "refund_eligibility"
        assert second["tool_used"] == "refund_eligibility_tool.check_refund_eligibility"
        assert second["data"]["order_id"] == "ORD10003"
        assert get_session(first["session_id"])["conversation_status"] == SESSION_STATUS_COMPLETED
        assert "pending_task_resumed" in {event["action_type"] for event in list_trace_events("resume-refund-2")}


def test_order_lookup_missing_order_id_then_resume_lookup() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("帮我查询订单状态", request_id="resume-order-1")
        second = run_after_sales_agent("ORD10003", session_id=first["session_id"], request_id="resume-order-2")

        assert first["answer_status"] == "missing_order_id"
        assert get_session(first["session_id"])["conversation_status"] == SESSION_STATUS_COMPLETED
        assert second["intent"] == "order_lookup"
        assert second["tool_used"] == "order_tool.get_order"
        assert second["data"]["order_id"] == "ORD10003"


def test_create_ticket_missing_order_id_then_enters_confirmation_without_write() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("帮我创建售后工单", request_id="resume-ticket-1")
        second = run_after_sales_agent("ORD10003", session_id=first["session_id"], request_id="resume-ticket-2")

        assert first["answer_status"] == "missing_order_id"
        assert second["intent"] == "create_ticket"
        assert second["answer_status"] == "ticket_confirmation_required"
        assert second["confirmation_required"] is True
        assert second["tool_used"] is None
        assert list_tickets("ORD10003") == []
        session = get_session(first["session_id"])
        assert session["conversation_status"] == SESSION_STATUS_PENDING
        assert session["pending_action"] == "create_ticket"
        assert session["pending_order_id"] == "ORD10003"


def test_composite_missing_order_id_then_resume_workflow_and_confirm_ticket() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("订单能退吗，不行就建工单", request_id="resume-workflow-1")
        second = run_after_sales_agent("ORD10003", session_id=first["session_id"], request_id="resume-workflow-2")
        third = run_after_sales_agent("确认", session_id=first["session_id"], request_id="resume-workflow-3")

        assert first["intent"] == "refund_then_ticket_if_ineligible"
        assert first["answer_status"] == "missing_order_id"
        assert second["intent"] == "refund_then_ticket_if_ineligible"
        assert second["answer_status"] == "ticket_confirmation_required"
        assert second["tool_used"] == "refund_eligibility_tool.check_refund_eligibility"
        assert third["tool_used"] == "order_tool.create_ticket"
        assert third["data"]["ticket"]["order_id"] == "ORD10003"
        assert len(list_tickets("ORD10003")) == 1


def test_cancel_awaiting_order_id_clears_pending_without_tool_call() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("帮我退款", request_id="resume-cancel-1")
        cancelled = run_after_sales_agent("取消", session_id=first["session_id"], request_id="resume-cancel-2")

        assert cancelled["intent"] == "session_control"
        assert cancelled["tool_used"] is None
        assert get_session(first["session_id"])["conversation_status"] == SESSION_STATUS_CANCELLED
        assert "pending_task_cancelled" in {event["action_type"] for event in list_trace_events("resume-cancel-2")}


def test_new_policy_question_interrupts_awaiting_order_id_task() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("帮我退款", request_id="resume-interrupt-1")
        second = run_after_sales_agent(
            "那我问一下保修多久",
            session_id=first["session_id"],
            request_id="resume-interrupt-2",
            policy_qa_callable=policy_qa_stub,
        )

        assert second["intent"] == "policy_qa"
        assert second["tool_used"] == "policy_qa_tool.ask_policy_question"
        assert get_session(first["session_id"])["conversation_status"] == SESSION_STATUS_INTERRUPTED
        assert "pending_task_interrupted" in {event["action_type"] for event in list_trace_events("resume-interrupt-2")}


def test_order_id_completion_is_isolated_by_session() -> None:
    with isolated_demo_database():
        session_a = run_after_sales_agent("帮我退款", session_id="resume-session-a")
        session_b = run_after_sales_agent("ORD10003", session_id="resume-session-b")

        assert get_session(session_a["session_id"])["pending_action"] == "refund_eligibility"
        assert session_b["intent"] == "order_lookup"
        assert session_b["tool_used"] == "order_tool.get_order"
        assert get_session("resume-session-b")["conversation_status"] == SESSION_STATUS_IDLE


def test_repeated_order_id_completion_after_create_ticket_resume_does_not_write_ticket() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("帮我创建售后工单")
        second = run_after_sales_agent("ORD10003", session_id=first["session_id"])
        repeated = run_after_sales_agent("ORD10003", session_id=first["session_id"])

        assert second["answer_status"] == "ticket_confirmation_required"
        assert repeated["intent"] == "order_lookup"
        assert repeated["tool_used"] == "order_tool.get_order"
        assert list_tickets("ORD10003") == []
