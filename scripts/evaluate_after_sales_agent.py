"""
离线评测售后 Agent 的路由、工具选择、实体抽取、结构化输出和安全门控。

本脚本不会调用真实 LLM。政策问答路径使用 stub，仅验证 Agent 是否正确路由、
是否保留引用/证据字段，以及响应 schema 是否稳定。
"""

from __future__ import annotations

import json
import gc
import sqlite3
import sys
import tempfile
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

import app.tools.order_tool as order_tool_module
import scripts.init_demo_data as demo_data_module
from app.agent.after_sales_agent_service import run_after_sales_agent
from app.schemas.after_sales_agent_schema import AfterSalesAgentResponse
from app.services.trace_store import list_trace_events


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "eval" / "after_sales_agent_eval_questions.jsonl"
RESULTS_DIR = PROJECT_ROOT / "eval_results"

METRIC_KEYS = [
    "intent_accuracy",
    "route_or_status_accuracy",
    "tool_selection_accuracy",
    "entity_extraction_accuracy",
    "safety_gate_pass_rate",
    "response_schema_valid_rate",
    "end_to_end_success_rate",
]


def policy_qa_stub(query: str) -> dict[str, Any]:
    """
    离线评测专用政策 QA stub。

    这里故意不评估自然语言答案质量，只提供合法的引用和证据结构，
    让评测聚焦 Agent 路由、工具调用和响应格式。
    """
    return {
        "success": True,
        "query": query,
        "answer_status": "answered",
        "answer": "这是政策问答 stub 返回，用于离线评测路由和结构化字段，不评价真实 LLM 文案。",
        "retrieval_mode": "stub",
        "retrieved_chunks": [
            {
                "chunk_id": "stub-policy-1",
                "source_file": "stub_policy.md",
                "section_title": "离线评测证据",
                "score": 1.0,
            }
        ],
        "citations": [
            {
                "chunk_id": "stub-policy-1",
                "source_file": "stub_policy.md",
                "section_title": "离线评测证据",
            }
        ],
        "has_relevant_policy": True,
        "generation": None,
        "grounding_verification": {"passed": True, "reason": "stub"},
        "message": "stub",
        "error": None,
        "debug": {"llm_called": False},
    }


def policy_qa_retry_success_stub(query: str) -> dict[str, Any]:
    result = policy_qa_stub(query)
    result["debug"] = {
        "llm_called": True,
        "retry_count": 1,
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
                "action_type": "retry_success",
                "status": "success",
                "retry_count": 1,
                "latency_ms": 1,
            },
        ],
    }
    return result


def policy_qa_degraded_stub(query: str) -> dict[str, Any]:
    result = policy_qa_stub(query)
    result.update(
        {
            "success": True,
            "answer_status": "degraded",
            "answer": "当前政策回答服务暂时不可用，以下仅返回已检索到的模拟政策依据摘要。",
            "generation": None,
            "grounding_verification": {"passed": False, "reason": "degraded"},
            "message": "模型生成失败，已安全降级。",
            "error": "timeout",
        }
    )
    result["debug"] = {
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
    }
    return result


def choose_policy_stub(item: dict[str, Any]):
    mode = item.get("policy_stub_mode")
    if mode == "retry_success":
        return policy_qa_retry_success_stub
    if mode == "degraded":
        return policy_qa_degraded_stub
    return policy_qa_stub


def load_questions(eval_file: Path = EVAL_FILE) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    with eval_file.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            item.setdefault("expected", normalize_expected(item))
            item["_line_number"] = line_number
            questions.append(item)
    return questions


def normalize_expected(item: dict[str, Any]) -> dict[str, Any]:
    expected = dict(item.get("expected") or {})
    if "expected_intent" in item:
        expected["intent"] = item["expected_intent"]
    if "expected_tool" in item:
        expected["tool_used"] = item["expected_tool"]
    if "expected_order_id" in item:
        expected["order_id"] = item["expected_order_id"]
    if "expected_order_ids" in item:
        expected["order_ids"] = item["expected_order_ids"]
    if "expected_status" in item:
        expected["answer_status"] = item["expected_status"]
    if "expected_route" in item:
        expected["route"] = item["expected_route"]
    if "expected_trace_found" in item:
        expected["trace_found"] = item["expected_trace_found"]
    return expected


def is_match(actual: Any, expected: Any) -> bool:
    if expected is None:
        return actual is None
    return actual == expected


def validate_response_schema(response: dict[str, Any]) -> tuple[bool, list[str]]:
    try:
        AfterSalesAgentResponse.model_validate(response)
    except Exception as exc:  # pragma: no cover - pydantic gives detailed messages.
        return False, [f"response_schema_invalid: {exc}"]

    extra_errors: list[str] = []
    if not isinstance(response.get("tool_trace"), list):
        extra_errors.append("tool_trace_not_list")
    if not isinstance(response.get("citations"), list):
        extra_errors.append("citations_not_list")
    if not isinstance(response.get("data"), dict):
        extra_errors.append("data_not_dict")
    if not isinstance(response.get("debug"), dict):
        extra_errors.append("debug_not_dict")
    return not extra_errors, extra_errors


def derive_actual_route(response: dict[str, Any]) -> str:
    tool_used = response.get("tool_used")
    answer_status = response.get("answer_status")
    intent = response.get("intent")

    if answer_status == "missing_order_id":
        return "ask_for_order_id"
    if answer_status == "ticket_confirmation_required":
        return "ticket_confirmation"
    if tool_used == "policy_qa_tool.ask_policy_question":
        return "policy_qa"
    if tool_used == "order_tool.get_order":
        return "order_lookup"
    if tool_used == "refund_eligibility_tool.check_refund_eligibility":
        return "refund_eligibility"
    if tool_used == "order_tool.create_ticket":
        return "create_ticket"
    if intent == "human_handoff":
        return "human_handoff"
    if intent == "unknown":
        return "unknown"
    return str(intent or "unknown")


def get_ticket_count(database_path: Path) -> int:
    with sqlite3.connect(database_path) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM tickets")
        return int(cursor.fetchone()[0])


@contextmanager
def isolated_demo_database() -> Iterator[Path]:
    """
    在临时目录初始化一份订单库，避免评测工单写入本地演示数据库。

    订单 Tool 通过 get_database_path 动态定位 SQLite，因此这里临时替换
    init 脚本和 Tool 模块中的路径函数；退出上下文后立即恢复。
    """
    original_demo_path_getter = demo_data_module.get_database_path
    original_order_path_getter = order_tool_module.get_database_path

    with tempfile.TemporaryDirectory(
        prefix="after_sales_agent_eval_",
        ignore_cleanup_errors=True,
    ) as temp_dir:
        database_path = Path(temp_dir) / "orders_eval.db"
        demo_data_module.get_database_path = lambda: database_path  # type: ignore[assignment]
        order_tool_module.get_database_path = lambda: database_path  # type: ignore[assignment]
        try:
            demo_data_module.initialize_database()
            yield database_path
        finally:
            demo_data_module.get_database_path = original_demo_path_getter  # type: ignore[assignment]
            order_tool_module.get_database_path = original_order_path_getter  # type: ignore[assignment]
            # Windows 下 sqlite 文件句柄有时会在函数返回后短暂滞留；
            # 这里显式触发回收并稍等，避免临时库清理影响评测结果。
            gc.collect()
            time.sleep(0.2)


def check_entity_extraction(response: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str | None]:
    actual_order_ids = response.get("debug", {}).get("all_detected_order_ids", [])
    actual_first_order_id = actual_order_ids[0] if actual_order_ids else None

    if "order_ids" in expected:
        expected_order_ids = expected.get("order_ids") or []
        if actual_order_ids == expected_order_ids:
            return True, None
        return False, f"order_ids expected={expected_order_ids} actual={actual_order_ids}"

    expected_order_id = expected.get("order_id")
    if is_match(actual_first_order_id, expected_order_id):
        return True, None
    return False, f"order_id expected={expected_order_id} actual={actual_first_order_id}"


def check_policy_evidence(item: dict[str, Any], response: dict[str, Any]) -> tuple[bool | None, list[str]]:
    if item.get("category") != "policy_qa":
        return None, []

    citations = response.get("citations") or []
    policy_data = response.get("data", {}).get("policy_qa", {})
    verification = policy_data.get("grounding_verification") or {}
    errors: list[str] = []
    if not citations:
        errors.append("policy_citation_missing")
    if policy_data.get("has_relevant_policy") is not True:
        errors.append("policy_relevance_missing")
    if verification.get("passed") is not True:
        errors.append("policy_grounding_not_passed")
    return not errors, errors


def check_safety_gate(
    item: dict[str, Any],
    response: dict[str, Any],
    before_ticket_count: int,
    after_ticket_count: int,
) -> tuple[bool | None, list[str]]:
    safety = item.get("expected_safety") or {}
    if not safety:
        return None, []

    errors: list[str] = []
    tool_used = response.get("tool_used")

    if safety.get("no_write") and after_ticket_count != before_ticket_count:
        errors.append("safety_no_write_failed")
    if safety.get("write_ticket") and after_ticket_count <= before_ticket_count:
        errors.append("safety_expected_ticket_write_missing")
    if safety.get("no_refund_tool") and tool_used == "refund_eligibility_tool.check_refund_eligibility":
        errors.append("safety_refund_tool_called")
    if safety.get("no_ticket_tool") and tool_used == "order_tool.create_ticket":
        errors.append("safety_ticket_tool_called")
    if safety.get("missing_order_id_no_tool") and tool_used is not None:
        errors.append("safety_missing_order_id_called_tool")
    if safety.get("human_handoff") and response.get("intent") != "human_handoff":
        errors.append("safety_human_handoff_not_reached")
    if safety.get("confirmation_required") and response.get("confirmation_required") is not True:
        errors.append("safety_confirmation_flag_missing")

    return not errors, errors


TRACE_REQUIRED_FIELDS = {
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


def check_trace_expectation(item: dict[str, Any], response: dict[str, Any]) -> tuple[bool | None, list[str]]:
    expected_trace = item.get("expected_trace") or {}
    if not expected_trace:
        return None, []

    events = list_trace_events(response.get("request_id", ""))
    errors: list[str] = []
    if expected_trace.get("persisted") and not events:
        errors.append("trace_not_persisted")
    if expected_trace.get("schema"):
        for event in events:
            missing_fields = TRACE_REQUIRED_FIELDS - set(event.keys())
            if missing_fields:
                errors.append(f"trace_schema_missing_fields={sorted(missing_fields)}")
                break
    if expected_trace.get("no_sensitive"):
        combined_text = json.dumps(events, ensure_ascii=False)
        forbidden_fragments = [
            "ORD10003",
            "ORD10004",
            "ORD10005",
            "api_key",
            "password",
            "sk-",
            "验证码",
            "银行卡",
        ]
        for fragment in forbidden_fragments:
            if fragment in combined_text:
                errors.append(f"trace_sensitive_fragment_leaked={fragment}")
                break
    if expected_trace.get("action_types"):
        action_types = {event.get("action_type") for event in events}
        missing_action_types = set(expected_trace["action_types"]) - action_types
        if missing_action_types:
            errors.append(f"trace_action_types_missing={sorted(missing_action_types)}")
    return not errors, errors


def check_retry_expectation(item: dict[str, Any], response: dict[str, Any]) -> tuple[bool | None, list[str]]:
    expected_retry = item.get("expected_retry") or {}
    if not expected_retry:
        return None, []
    errors: list[str] = []
    if response.get("retry_count") != expected_retry.get("retry_count"):
        errors.append(
            f"retry_count expected={expected_retry.get('retry_count')} actual={response.get('retry_count')}"
        )
    if "degraded" in expected_retry and response.get("degraded") is not expected_retry["degraded"]:
        errors.append(f"degraded expected={expected_retry['degraded']} actual={response.get('degraded')}")
    if expected_retry.get("fallback_action") and response.get("fallback_action") != expected_retry["fallback_action"]:
        errors.append(
            f"fallback_action expected={expected_retry['fallback_action']} actual={response.get('fallback_action')}"
        )
    if expected_retry.get("error_category") and response.get("error_category") != expected_retry["error_category"]:
        errors.append(
            f"error_category expected={expected_retry['error_category']} actual={response.get('error_category')}"
        )
    return not errors, errors


def check_workflow_expectation(item: dict[str, Any], response: dict[str, Any]) -> tuple[bool | None, list[str]]:
    expected_workflow = item.get("expected_workflow") or {}
    if not expected_workflow:
        return None, []

    summary = response.get("workflow_summary") or response.get("data", {}).get("workflow_summary") or {}
    errors: list[str] = []
    for key, expected_value in expected_workflow.items():
        actual_value = summary.get(key)
        if actual_value != expected_value:
            errors.append(f"workflow_{key}_mismatch expected={expected_value} actual={actual_value}")
    return not errors, errors


def evaluate_trace_lookup_question(item: dict[str, Any], database_path: Path) -> dict[str, Any]:
    events = list_trace_events(item["trace_lookup_request_id"])
    expected = normalize_expected(item)
    expected_found = expected.get("trace_found", False)
    found = bool(events)
    checks = {
        "intent": None,
        "route_or_status": found is expected_found,
        "tool_used": None,
        "entity_extraction": None,
        "safety_gate": True,
        "response_schema": True,
        "policy_evidence": None,
        "trace": found is expected_found,
        "workflow": None,
    }
    failure_reasons = []
    if checks["trace"] is False:
        failure_reasons.append(
            {
                "type": "trace_lookup_mismatch",
                "message": f"expected_found={expected_found} actual_found={found}",
            }
        )
    return {
        "id": item["id"],
        "category": item.get("category", "observability"),
        "query": item.get("query", ""),
        "notes": item.get("notes", ""),
        "confirm_ticket_creation": False,
        "expected": expected,
        "actual": {
            "trace_found": found,
            "trace_event_count": len(events),
            "request_id": item["trace_lookup_request_id"],
        },
        "checks": checks,
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "ticket_count_before": get_ticket_count(database_path),
        "ticket_count_after": get_ticket_count(database_path),
        "elapsed_seconds": 0,
    }


def evaluate_question(item: dict[str, Any], database_path: Path) -> dict[str, Any]:
    if item.get("trace_lookup_request_id"):
        return evaluate_trace_lookup_question(item, database_path)
    if item.get("conversation_steps"):
        return evaluate_conversation_question(item, database_path)

    expected = normalize_expected(item)
    before_ticket_count = get_ticket_count(database_path)
    started_at = time.perf_counter()

    response = run_after_sales_agent(
        item["query"],
        confirm_ticket_creation=bool(item.get("confirm_ticket_creation", False)),
        request_id=item["id"],
        policy_qa_callable=choose_policy_stub(item),
        session_id=item.get("session_id"),
        idempotency_key=item.get("idempotency_key"),
    )

    elapsed_seconds = round(time.perf_counter() - started_at, 4)
    after_ticket_count = get_ticket_count(database_path)
    actual_order_ids = response.get("debug", {}).get("all_detected_order_ids", [])
    actual_first_order_id = actual_order_ids[0] if actual_order_ids else None
    actual_route = derive_actual_route(response)

    schema_valid, schema_errors = validate_response_schema(response)
    entity_ok, entity_error = check_entity_extraction(response, expected)
    safety_ok, safety_errors = check_safety_gate(
        item=item,
        response=response,
        before_ticket_count=before_ticket_count,
        after_ticket_count=after_ticket_count,
    )
    policy_evidence_ok, policy_evidence_errors = check_policy_evidence(item, response)
    trace_ok, trace_errors = check_trace_expectation(item, response)
    retry_ok, retry_errors = check_retry_expectation(item, response)
    workflow_ok, workflow_errors = check_workflow_expectation(item, response)

    checks: dict[str, bool | None] = {
        "intent": is_match(response.get("intent"), expected.get("intent")),
        "route_or_status": (
            is_match(actual_route, expected.get("route"))
            and is_match(response.get("answer_status"), expected.get("answer_status"))
        ),
        "tool_used": is_match(response.get("tool_used"), expected.get("tool_used")),
        "entity_extraction": entity_ok,
        "safety_gate": safety_ok,
        "response_schema": schema_valid,
        "policy_evidence": policy_evidence_ok,
        "trace": trace_ok,
        "retry_degradation": retry_ok,
        "workflow": workflow_ok,
    }

    failure_reasons: list[dict[str, str]] = []
    if checks["intent"] is False:
        failure_reasons.append(
            {
                "type": "intent_mismatch",
                "message": f"expected={expected.get('intent')} actual={response.get('intent')}",
            }
        )
    if checks["route_or_status"] is False:
        failure_reasons.append(
            {
                "type": "route_or_status_mismatch",
                "message": (
                    f"expected_route={expected.get('route')} actual_route={actual_route}; "
                    f"expected_status={expected.get('answer_status')} actual_status={response.get('answer_status')}"
                ),
            }
        )
    if checks["tool_used"] is False:
        failure_reasons.append(
            {
                "type": "tool_selection_mismatch",
                "message": f"expected={expected.get('tool_used')} actual={response.get('tool_used')}",
            }
        )
    if not entity_ok and entity_error:
        failure_reasons.append({"type": "entity_extraction_mismatch", "message": entity_error})
    for safety_error in safety_errors:
        failure_reasons.append({"type": safety_error, "message": safety_error})
    for schema_error in schema_errors:
        failure_reasons.append({"type": "response_schema_invalid", "message": schema_error})
    for policy_error in policy_evidence_errors:
        failure_reasons.append({"type": policy_error, "message": policy_error})
    for trace_error in trace_errors:
        failure_reasons.append({"type": trace_error, "message": trace_error})
    for retry_error in retry_errors:
        failure_reasons.append({"type": "retry_degradation_mismatch", "message": retry_error})
    for workflow_error in workflow_errors:
        failure_reasons.append({"type": "workflow_mismatch", "message": workflow_error})

    applicable_checks = [value for value in checks.values() if value is not None]
    passed = bool(applicable_checks) and all(applicable_checks)

    return {
        "id": item["id"],
        "category": item.get("category", "uncategorized"),
        "query": item["query"],
        "notes": item.get("notes", ""),
        "confirm_ticket_creation": bool(item.get("confirm_ticket_creation", False)),
        "expected": expected,
        "actual": {
            "intent": response.get("intent"),
            "route": actual_route,
            "tool_used": response.get("tool_used"),
            "order_id": actual_first_order_id,
            "order_ids": actual_order_ids,
            "answer_status": response.get("answer_status"),
            "needs_human_review": response.get("needs_human_review"),
            "confirmation_required": response.get("confirmation_required"),
            "citation_count": len(response.get("citations") or []),
            "session_id": response.get("session_id"),
            "idempotency_key": response.get("debug", {}).get("idempotency_key"),
            "trace_event_count": len(list_trace_events(response.get("request_id", ""))),
            "retry_count": response.get("retry_count"),
            "degraded": response.get("degraded"),
            "error_category": response.get("error_category"),
            "fallback_action": response.get("fallback_action"),
            "workflow_type": (response.get("workflow_summary") or {}).get("workflow_type"),
            "plan_status": (response.get("workflow_summary") or {}).get("plan_status"),
            "current_step": (response.get("workflow_summary") or {}).get("current_step"),
            "next_action": (response.get("workflow_summary") or {}).get("next_action"),
        },
        "checks": checks,
        "passed": passed,
        "failure_reasons": failure_reasons,
        "ticket_count_before": before_ticket_count,
        "ticket_count_after": after_ticket_count,
        "elapsed_seconds": elapsed_seconds,
    }


def evaluate_conversation_question(item: dict[str, Any], database_path: Path) -> dict[str, Any]:
    started_at = time.perf_counter()
    step_results: list[dict[str, Any]] = []
    saved_sessions: dict[str, str] = {}
    shared_session_id: str | None = item.get("session_id")

    for index, step in enumerate(item["conversation_steps"], start=1):
        step_item = {
            **step,
            "id": f"{item['id']}.{index}",
            "category": item.get("category", "ticket_safety"),
            "notes": step.get("notes", item.get("notes", "")),
        }
        session_ref = step.get("use_session_from")
        if session_ref:
            step_item["session_id"] = saved_sessions.get(session_ref)
        elif step.get("use_previous_session"):
            step_item["session_id"] = shared_session_id
        elif step.get("session_id"):
            step_item["session_id"] = step["session_id"]

        step_result = evaluate_question(step_item, database_path)
        step_results.append(step_result)

        actual_session_id = step_result["actual"].get("session_id")
        if actual_session_id and shared_session_id is None:
            shared_session_id = actual_session_id
        if step.get("save_session_as") and actual_session_id:
            saved_sessions[step["save_session_as"]] = actual_session_id

    aggregate_checks: dict[str, bool | None] = {}
    for check_name in [
        "intent",
        "route_or_status",
        "tool_used",
        "entity_extraction",
        "safety_gate",
        "response_schema",
        "policy_evidence",
        "trace",
        "retry_degradation",
        "workflow",
    ]:
        values = [
            step_result["checks"].get(check_name)
            for step_result in step_results
            if step_result["checks"].get(check_name) is not None
        ]
        aggregate_checks[check_name] = all(values) if values else None

    failure_reasons: list[dict[str, str]] = []
    for step_result in step_results:
        for reason in step_result["failure_reasons"]:
            failure_reasons.append(
                {
                    "type": reason["type"],
                    "message": f"{step_result['id']}: {reason['message']}",
                }
            )

    applicable_checks = [value for value in aggregate_checks.values() if value is not None]
    return {
        "id": item["id"],
        "category": item.get("category", "ticket_safety"),
        "query": " -> ".join(step["query"] for step in item["conversation_steps"]),
        "notes": item.get("notes", ""),
        "confirm_ticket_creation": False,
        "expected": {"conversation_steps": [normalize_expected(step) for step in item["conversation_steps"]]},
        "actual": {"conversation_steps": [step_result["actual"] for step_result in step_results]},
        "checks": aggregate_checks,
        "passed": bool(applicable_checks) and all(applicable_checks),
        "failure_reasons": failure_reasons,
        "ticket_count_before": step_results[0]["ticket_count_before"] if step_results else 0,
        "ticket_count_after": step_results[-1]["ticket_count_after"] if step_results else 0,
        "elapsed_seconds": round(time.perf_counter() - started_at, 4),
    }


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def calculate_metric(results: list[dict[str, Any]], check_name: str) -> float:
    applicable = [item for item in results if item["checks"].get(check_name) is not None]
    passed = [item for item in applicable if item["checks"].get(check_name) is True]
    return ratio(len(passed), len(applicable))


def calculate_metric_detail(results: list[dict[str, Any]], check_name: str) -> dict[str, Any]:
    applicable = [item for item in results if item["checks"].get(check_name) is not None]
    passed = [item for item in applicable if item["checks"].get(check_name) is True]
    return {
        "passed_count": len(passed),
        "applicable_count": len(applicable),
        "rate": ratio(len(passed), len(applicable)),
    }


def calculate_summary(
    results: list[dict[str, Any]],
    total_elapsed_seconds: float,
    database_path: Path,
) -> dict[str, Any]:
    total = len(results)
    category_summary: dict[str, Any] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[item["category"]].append(item)

    for category, category_items in sorted(grouped.items()):
        category_summary[category] = {
            "total": len(category_items),
            "passed": sum(1 for item in category_items if item["passed"]),
            "pass_rate": ratio(sum(1 for item in category_items if item["passed"]), len(category_items)),
        }

    failure_type_counter: Counter[str] = Counter()
    for item in results:
        for reason in item["failure_reasons"]:
            failure_type_counter[reason["type"]] += 1

    metrics = {
        "intent_accuracy": calculate_metric(results, "intent"),
        "route_or_status_accuracy": calculate_metric(results, "route_or_status"),
        "tool_selection_accuracy": calculate_metric(results, "tool_used"),
        "entity_extraction_accuracy": calculate_metric(results, "entity_extraction"),
        "safety_gate_pass_rate": calculate_metric(results, "safety_gate"),
        "response_schema_valid_rate": calculate_metric(results, "response_schema"),
        "end_to_end_success_rate": ratio(sum(1 for item in results if item["passed"]), total),
    }
    metric_details = {
        "intent_accuracy": calculate_metric_detail(results, "intent"),
        "route_or_status_accuracy": calculate_metric_detail(results, "route_or_status"),
        "tool_selection_accuracy": calculate_metric_detail(results, "tool_used"),
        "entity_extraction_accuracy": calculate_metric_detail(results, "entity_extraction"),
        "safety_gate_pass_rate": calculate_metric_detail(results, "safety_gate"),
        "response_schema_valid_rate": calculate_metric_detail(results, "response_schema"),
        "end_to_end_success_rate": {
            "passed_count": sum(1 for item in results if item["passed"]),
            "applicable_count": total,
            "rate": ratio(sum(1 for item in results if item["passed"]), total),
        },
    }

    return {
        "evaluated_at": datetime.now().replace(microsecond=0).isoformat(),
        "total_samples": total,
        "passed_samples": sum(1 for item in results if item["passed"]),
        "failed_samples": sum(1 for item in results if not item["passed"]),
        "metrics": metrics,
        "metric_details": metric_details,
        "category_summary": category_summary,
        "top_badcases": [
            {"failure_type": failure_type, "count": count}
            for failure_type, count in failure_type_counter.most_common()
        ],
        "runtime_seconds": round(total_elapsed_seconds, 2),
        "evaluation_mode": {
            "calls_real_llm": False,
            "policy_qa": "stub",
            "uses_isolated_database": True,
            "isolated_database_path": str(database_path),
            "notes": "工单写入仅发生在临时 SQLite，脚本结束后自动清理。",
        },
    }


def write_outputs(results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results_path = RESULTS_DIR / "after_sales_agent_eval_results.jsonl"
    with results_path.open("w", encoding="utf-8") as file:
        for item in results:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    (RESULTS_DIR / "after_sales_agent_eval_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    failed_items = [item for item in results if not item["passed"]]
    lines = [
        "# 售后 Agent 离线自动评测报告",
        "",
        f"- 评测时间：{summary['evaluated_at']}",
        f"- 总样本数：{summary['total_samples']}",
        f"- 通过样本数：{summary['passed_samples']}",
        f"- 失败样本数：{summary['failed_samples']}",
        f"- 运行耗时：{summary['runtime_seconds']} 秒",
        "- 评测模式：不调用真实 LLM；政策问答使用 stub；工单写入隔离临时 SQLite。",
        "",
        "## 核心指标",
        "",
    ]
    for key in METRIC_KEYS:
        detail = summary["metric_details"][key]
        lines.append(
            f"- {key}: {detail['passed_count']}/{detail['applicable_count']}，rate={detail['rate']:.4f}"
        )
    lines.append("- 说明：部分指标只对相关样本适用，因此 applicable_count 可能小于总样本数。")

    lines.extend(["", "## 分类通过率", ""])
    for category, item in summary["category_summary"].items():
        lines.append(
            f"- {category}: {item['passed']}/{item['total']}，pass_rate={item['pass_rate']:.4f}"
        )

    lines.extend(["", "## Top Badcases", ""])
    if summary["top_badcases"]:
        for item in summary["top_badcases"]:
            lines.append(f"- {item['failure_type']}: {item['count']}")
    else:
        lines.append("- 暂无失败类型。")

    lines.extend(["", "## 失败样本", ""])
    if not failed_items:
        lines.append("- 暂无失败样本。")
    for item in failed_items:
        reason_text = "; ".join(reason["message"] for reason in item["failure_reasons"])
        lines.extend(
            [
                f"### {item['id']} / {item['category']}",
                "",
                f"- query: {item['query']}",
                f"- expected: `{json.dumps(item['expected'], ensure_ascii=False)}`",
                f"- actual: `{json.dumps(item['actual'], ensure_ascii=False)}`",
                f"- failure_reason: {reason_text}",
                f"- notes: {item.get('notes', '')}",
                "",
            ]
        )

    lines.extend(
        [
            "## 需要人工复核的内容",
            "",
            "- 政策问答的自然语言答案质量没有做字符串精确匹配，也没有使用 LLM-as-a-Judge。",
            "- 该报告只能证明离线路由、工具、实体、schema 和安全门控是否符合预期。",
            "- 当前失败样本应作为真实 badcase 保留，不应通过删除样本提升分数。",
        ]
    )
    (RESULTS_DIR / "after_sales_agent_eval_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    badcase_lines = ["# 售后 Agent Badcases", ""]
    if not failed_items:
        badcase_lines.append("暂无 badcase。")
    for item in failed_items:
        badcase_lines.append(f"- {item['id']} [{item['category']}]: {item['query']}")
        for reason in item["failure_reasons"]:
            badcase_lines.append(f"  - {reason['type']}: {reason['message']}")
    (RESULTS_DIR / "after_sales_agent_badcases.md").write_text(
        "\n".join(badcase_lines) + "\n",
        encoding="utf-8",
    )


def print_console_summary(summary: dict[str, Any]) -> None:
    print("售后 Agent 离线评测完成")
    print(f"总样本数: {summary['total_samples']}")
    print(f"通过/失败: {summary['passed_samples']} / {summary['failed_samples']}")
    for key in METRIC_KEYS:
        detail = summary["metric_details"][key]
        print(f"{key}: {detail['passed_count']}/{detail['applicable_count']} = {detail['rate']:.4f}")
    if summary["top_badcases"]:
        print("Top badcases:")
        for item in summary["top_badcases"]:
            print(f"- {item['failure_type']}: {item['count']}")


def main() -> None:
    start_time = time.perf_counter()
    questions = load_questions()

    with isolated_demo_database() as database_path:
        results = [evaluate_question(item, database_path) for item in questions]
        summary = calculate_summary(
            results=results,
            total_elapsed_seconds=time.perf_counter() - start_time,
            database_path=database_path,
        )

    write_outputs(results, summary)
    print_console_summary(summary)


if __name__ == "__main__":
    main()
