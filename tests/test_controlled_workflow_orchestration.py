"""Controlled composite workflow tests.

The workflow is deliberately small: refund eligibility is checked first, and
ticket creation is only offered as a persisted pending action when the order is
not directly refundable and the user explicitly requested that fallback.
"""

from __future__ import annotations

from app.agent.after_sales_agent_service import run_after_sales_agent
from app.agent.intent_classifier import classify_intent
from app.services.session_store import SESSION_STATUS_COMPLETED, get_session
from app.services.trace_store import list_trace_events
from app.tools.order_tool import list_tickets
from scripts.evaluate_after_sales_agent import isolated_demo_database


COMPOSITE_ELIGIBLE_QUERY = "ORD10004 能退款吗？如果不能，帮我创建售后工单。"
COMPOSITE_INELIGIBLE_QUERY = "ORD10003 能退款吗？如果不能，帮我创建售后工单。"


def test_compound_intent_recognition_and_high_risk_priority() -> None:
    normal = classify_intent(COMPOSITE_INELIGIBLE_QUERY, "ORD10003")
    assert normal["intent"] == "refund_then_ticket_if_ineligible"
    assert normal["requires_order_id"] is True

    high_risk = classify_intent(
        "ORD10003 能退款吗？如果不能帮我创建售后工单，我银行卡重复扣款了。",
        "ORD10003",
    )
    assert high_risk["intent"] == "human_handoff"


def test_compound_refund_eligible_does_not_create_ticket() -> None:
    with isolated_demo_database():
        result = run_after_sales_agent(COMPOSITE_ELIGIBLE_QUERY)

        assert result["intent"] == "refund_then_ticket_if_ineligible"
        assert result["answer_status"] == "answered"
        assert result["tool_used"] == "refund_eligibility_tool.check_refund_eligibility"
        assert result["confirmation_required"] is False
        assert result["workflow_summary"]["plan_status"] == "completed"
        assert result["workflow_summary"]["next_action"] == "refund_eligible_no_ticket"
        assert list_tickets("ORD10004") == []


def test_compound_refund_ineligible_requires_confirmation_without_write() -> None:
    with isolated_demo_database():
        result = run_after_sales_agent(COMPOSITE_INELIGIBLE_QUERY)

        assert result["intent"] == "refund_then_ticket_if_ineligible"
        assert result["answer_status"] == "ticket_confirmation_required"
        assert result["confirmation_required"] is True
        assert result["workflow_summary"]["plan_status"] == "waiting_confirmation"
        assert result["workflow_summary"]["next_action"] == "confirm_create_ticket"
        assert list_tickets("ORD10003") == []

        session = get_session(result["session_id"])
        assert session is not None
        assert session["pending_action"] == "create_ticket"
        assert session["pending_order_id"] == "ORD10003"
        assert session["pending_payload"]["workflow_type"] == "refund_then_ticket_if_ineligible"


def test_compound_confirmation_creates_once_and_reuses_on_repeat() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent(COMPOSITE_INELIGIBLE_QUERY)
        second = run_after_sales_agent("确认", session_id=first["session_id"])
        repeated = run_after_sales_agent("确认", session_id=first["session_id"])

        assert second["tool_used"] == "order_tool.create_ticket"
        assert second["data"]["ticket"]["order_id"] == "ORD10003"
        assert repeated["intent"] == "session_control"
        assert repeated["data"]["ticket"]["ticket_id"] == second["data"]["ticket"]["ticket_id"]
        assert len(list_tickets("ORD10003")) == 1
        assert get_session(first["session_id"])["conversation_status"] == SESSION_STATUS_COMPLETED


def test_compound_cancel_clears_pending_without_write() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent(COMPOSITE_INELIGIBLE_QUERY)
        cancelled = run_after_sales_agent("取消", session_id=first["session_id"])

        assert cancelled["intent"] == "session_control"
        assert cancelled["tool_used"] is None
        assert list_tickets("ORD10003") == []
        assert get_session(first["session_id"])["pending_action"] is None


def test_compound_missing_order_id_asks_first_and_calls_no_tool() -> None:
    with isolated_demo_database():
        result = run_after_sales_agent("能退款吗？如果不能，帮我创建售后工单。")

        assert result["intent"] == "refund_then_ticket_if_ineligible"
        assert result["answer_status"] == "missing_order_id"
        assert result["tool_used"] is None
        assert result["confirmation_required"] is False
        assert list_tickets() == []


def test_compound_order_not_found_stops_without_pending_action() -> None:
    with isolated_demo_database():
        result = run_after_sales_agent("ORD99999 能退款吗？如果不能，帮我创建售后工单。")

        assert result["intent"] == "refund_then_ticket_if_ineligible"
        assert result["answer_status"] == "manual_review"
        assert result["tool_used"] == "order_tool.get_order"
        assert result["workflow_summary"]["plan_status"] == "stopped"
        assert result["workflow_summary"]["next_action"] == "stop_order_not_found"
        assert get_session(result["session_id"])["pending_action"] is None
        assert list_tickets() == []


def test_compound_high_risk_stops_before_refund_and_ticket_tools() -> None:
    with isolated_demo_database():
        result = run_after_sales_agent(
            "ORD10003 能退款吗？如果不能，帮我创建售后工单，我银行卡重复扣款了。"
        )

        assert result["intent"] == "human_handoff"
        assert result["answer_status"] == "manual_review"
        assert result["tool_used"] is None
        assert list_tickets("ORD10003") == []


def test_compound_trace_contains_plan_events_and_is_sanitized() -> None:
    with isolated_demo_database():
        result = run_after_sales_agent(COMPOSITE_INELIGIBLE_QUERY, request_id="workflow-trace-pytest")
        events = list_trace_events("workflow-trace-pytest")

        action_types = {event["action_type"] for event in events}
        assert {"plan_created", "plan_step_started", "plan_step_completed", "plan_decision", "plan_waiting_confirmation"} <= action_types
        assert result["debug"]["trace_event_count"] == len(events)
        serialized = str(events)
        assert "ORD10003" not in serialized
        assert "ORD***" in serialized


def test_compound_session_isolation_between_sessions() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent(COMPOSITE_INELIGIBLE_QUERY, session_id="workflow-session-a")
        wrong_session = run_after_sales_agent("确认", session_id="workflow-session-b")

        assert wrong_session["tool_used"] is None
        assert list_tickets("ORD10003") == []

        correct_session = run_after_sales_agent("确认", session_id=first["session_id"])
        assert correct_session["tool_used"] == "order_tool.create_ticket"
        assert len(list_tickets("ORD10003")) == 1
