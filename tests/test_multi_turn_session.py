"""Multi-turn session, idempotency and trace tests.

All tests use an isolated SQLite database from the evaluator helper, so local
data/orders.db is not polluted.
"""

from __future__ import annotations

from app.agent.after_sales_agent_service import run_after_sales_agent
from app.services.idempotency_store import get_idempotency_record
from app.services.session_store import (
    SESSION_STATUS_CANCELLED,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_PENDING,
    clear_pending_action,
    get_or_create_session,
    get_session,
    save_pending_action,
)
from app.services.trace_store import list_trace_events
from app.tools.order_tool import list_tickets
from scripts.evaluate_after_sales_agent import isolated_demo_database


def test_session_store_saves_and_clears_pending_action() -> None:
    with isolated_demo_database():
        session = get_or_create_session("session-store-test")
        assert session["session_id"] == "session-store-test"
        assert session["conversation_status"] == "idle"

        pending = save_pending_action(
            session_id="session-store-test",
            pending_action="create_ticket",
            pending_order_id="ORD10003",
            pending_payload={"user_query": "create"},
        )
        assert pending["conversation_status"] == SESSION_STATUS_PENDING
        assert pending["pending_action"] == "create_ticket"
        assert pending["pending_order_id"] == "ORD10003"

        cleared = clear_pending_action("session-store-test", SESSION_STATUS_CANCELLED)
        assert cleared["conversation_status"] == SESSION_STATUS_CANCELLED
        assert cleared["pending_action"] is None
        assert cleared["pending_order_id"] is None


def test_multi_turn_confirm_creates_ticket_once_and_reuses_on_repeat() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("帮我给 ORD10003 创建售后工单")
        assert first["answer_status"] == "ticket_confirmation_required"
        assert first["confirmation_required"] is True
        assert first["session_id"]
        assert list_tickets("ORD10003") == []

        second = run_after_sales_agent("确认", session_id=first["session_id"])
        assert second["answer_status"] == "answered"
        assert second["tool_used"] == "order_tool.create_ticket"
        assert second["data"]["ticket"]["order_id"] == "ORD10003"
        assert len(list_tickets("ORD10003")) == 1

        repeated = run_after_sales_agent("确认", session_id=first["session_id"])
        assert repeated["intent"] == "session_control"
        assert repeated["tool_used"] == "order_tool.create_ticket"
        assert repeated["data"]["ticket"]["ticket_id"] == second["data"]["ticket"]["ticket_id"]
        assert len(list_tickets("ORD10003")) == 1
        assert get_session(first["session_id"])["conversation_status"] == SESSION_STATUS_COMPLETED


def test_multi_turn_cancel_does_not_create_ticket() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("帮我给 ORD10004 创建售后工单")
        cancelled = run_after_sales_agent("取消", session_id=first["session_id"])

        assert cancelled["intent"] == "session_control"
        assert cancelled["tool_used"] is None
        assert cancelled["data"]["conversation_status"] == SESSION_STATUS_CANCELLED
        assert list_tickets("ORD10004") == []


def test_confirm_without_pending_action_does_not_create_ticket() -> None:
    with isolated_demo_database():
        result = run_after_sales_agent("确认", session_id="empty-session")

        assert result["intent"] == "session_control"
        assert result["answer_status"] == "answered"
        assert result["tool_used"] is None
        assert list_tickets() == []


def test_session_isolation_between_two_sessions() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent("帮我给 ORD10003 创建售后工单", session_id="session-a")
        wrong_session = run_after_sales_agent("确认", session_id="session-b")

        assert first["session_id"] == "session-a"
        assert wrong_session["intent"] == "session_control"
        assert wrong_session["tool_used"] is None
        assert list_tickets("ORD10003") == []

        correct_session = run_after_sales_agent("确认", session_id=first["session_id"])
        assert correct_session["tool_used"] == "order_tool.create_ticket"
        assert len(list_tickets("ORD10003")) == 1


def test_create_ticket_missing_order_id_asks_first() -> None:
    with isolated_demo_database():
        result = run_after_sales_agent("请帮我创建售后工单")

        assert result["intent"] == "create_ticket"
        assert result["answer_status"] == "missing_order_id"
        assert result["tool_used"] is None
        assert result["confirmation_required"] is False
        assert list_tickets() == []


def test_same_idempotency_key_reuses_ticket_for_direct_submit() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent(
            "请帮我创建工单，订单号 ORD10003",
            confirm_ticket_creation=True,
            idempotency_key="pytest-fixed-idem-key",
        )
        second = run_after_sales_agent(
            "请帮我创建工单，订单号 ORD10003",
            confirm_ticket_creation=True,
            idempotency_key="pytest-fixed-idem-key",
        )

        assert first["tool_used"] == "order_tool.create_ticket"
        assert second["tool_used"] == "order_tool.create_ticket"
        assert first["data"]["ticket"]["ticket_id"] == second["data"]["ticket"]["ticket_id"]
        assert len(list_tickets("ORD10003")) == 1
        record = get_idempotency_record("pytest-fixed-idem-key")
        assert record is not None
        assert record["status"] == "completed"


def test_different_idempotency_keys_can_create_different_tickets() -> None:
    with isolated_demo_database():
        first = run_after_sales_agent(
            "请帮我创建工单，订单号 ORD10003",
            confirm_ticket_creation=True,
            idempotency_key="pytest-idem-a",
        )
        second = run_after_sales_agent(
            "请帮我创建工单，订单号 ORD10003",
            confirm_ticket_creation=True,
            idempotency_key="pytest-idem-b",
        )

        assert first["data"]["ticket"]["ticket_id"] != second["data"]["ticket"]["ticket_id"]
        assert len(list_tickets("ORD10003")) == 2


def test_persisted_trace_schema_and_sanitization() -> None:
    with isolated_demo_database():
        result = run_after_sales_agent("请查询 ORD10003 的订单状态", request_id="trace-pytest-1")
        events = list_trace_events("trace-pytest-1")

        assert result["debug"]["trace_event_count"] == len(events)
        assert events
        required_fields = {
            "request_id",
            "session_id",
            "step_index",
            "node_name",
            "action_type",
            "tool_name",
            "parameter_summary",
            "result_summary",
            "status",
            "latency_ms",
            "error_category",
            "retry_count",
            "created_at",
        }
        assert required_fields <= set(events[0].keys())
        serialized = str(events)
        assert "ORD10003" not in serialized
        assert "ORD***" in serialized


def test_missing_trace_returns_empty_list() -> None:
    with isolated_demo_database():
        assert list_trace_events("not-exist-request-id") == []


def test_retry_and_fallback_events_are_persisted_in_trace() -> None:
    def degraded_policy_stub(query: str) -> dict:
        return {
            "success": True,
            "query": query,
            "answer_status": "degraded",
            "answer": "当前政策回答服务暂时不可用，以下仅返回已检索到的模拟政策依据摘要。",
            "retrieval_mode": "stub",
            "retrieved_chunks": [],
            "citations": [{"chunk_id": "stub", "source_file": "stub.md", "section_title": "stub"}],
            "has_relevant_policy": True,
            "generation": None,
            "grounding_verification": {"passed": False, "reason": "degraded"},
            "message": "degraded",
            "error": "timeout",
            "debug": {
                "llm_called": True,
                "retry_count": 2,
                "degraded": True,
                "fallback_action": "return_retrieved_policy_evidence",
                "error_category": "llm_timeout",
                "retry_trace_events": [
                    {
                        "step": "policy_qa_tool.ask_policy_question",
                        "action_type": "retry_attempt",
                        "status": "error",
                        "retry_count": 1,
                        "error_category": "llm_timeout",
                        "latency_ms": 1,
                    },
                    {
                        "step": "policy_qa_tool.ask_policy_question",
                        "action_type": "retry_exhausted",
                        "status": "error",
                        "retry_count": 2,
                        "error_category": "llm_timeout",
                        "latency_ms": 1,
                    },
                    {
                        "step": "policy_qa_tool.ask_policy_question",
                        "action_type": "fallback",
                        "status": "degraded",
                        "retry_count": 2,
                        "error_category": "llm_timeout",
                        "fallback_action": "return_retrieved_policy_evidence",
                        "degraded": True,
                        "latency_ms": 0,
                    },
                ],
            },
        }

    with isolated_demo_database():
        result = run_after_sales_agent(
            "耳机保修多久？",
            request_id="trace-retry-fallback",
            policy_qa_callable=degraded_policy_stub,
        )
        events = list_trace_events("trace-retry-fallback")

        assert result["answer_status"] == "degraded"
        assert result["retry_count"] == 2
        assert result["degraded"] is True
        action_types = {event["action_type"] for event in events}
        assert "retry_attempt" in action_types
        assert "retry_exhausted" in action_types
        assert "fallback" in action_types
        assert "llm_timeout" in str(events)
