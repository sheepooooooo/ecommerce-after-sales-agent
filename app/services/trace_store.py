"""Persisted, sanitized execution trace storage for the after-sales Agent."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any

import app.tools.order_tool as order_tool_module


MAX_SUMMARY_LENGTH = 500
SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{3,}"),
    re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*[^,\s}]+"),
    re.compile(r"\b\d{12,19}\b"),
    re.compile(r"\b\d{6}\b"),
]
ORDER_ID_PATTERN = re.compile(r"\bORD\d{5}\b", re.IGNORECASE)


def _now_text() -> str:
    return datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _connect() -> sqlite3.Connection:
    database_path = order_tool_module.get_database_path()
    order_tool_module.ensure_database_exists(database_path)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    ensure_trace_table(connection)
    return connection


def ensure_trace_table(connection: sqlite3.Connection | None = None) -> None:
    """Create the structured trace table if the current database is older."""
    owns_connection = connection is None
    active_connection = connection or sqlite3.connect(order_tool_module.get_database_path())
    try:
        active_connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_trace_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                node_name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                tool_name TEXT,
                parameter_summary TEXT NOT NULL,
                result_summary TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL NOT NULL DEFAULT 0,
                error_category TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        active_connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_trace_request_id ON agent_trace_events(request_id)"
        )
        active_connection.commit()
    finally:
        if owns_connection:
            active_connection.close()


def sanitize_value(value: Any) -> Any:
    """Recursively mask business identifiers and common secret-looking values."""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        sanitized = ORDER_ID_PATTERN.sub("ORD***", value)
        for pattern in SENSITIVE_PATTERNS:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        if len(sanitized) > MAX_SUMMARY_LENGTH:
            return sanitized[:MAX_SUMMARY_LENGTH] + "...[truncated]"
        return sanitized
    if isinstance(value, list):
        return [sanitize_value(item) for item in value[:20]]
    if isinstance(value, tuple):
        return [sanitize_value(item) for item in value[:20]]
    if isinstance(value, dict):
        sanitized_dict: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if re.search(r"(?i)(api[_-]?key|password|secret|token)", key_text):
                sanitized_dict[key_text] = "[REDACTED]"
            else:
                sanitized_dict[key_text] = sanitize_value(item)
        return sanitized_dict
    return sanitize_value(str(value))


def _summary_text(value: Any) -> str:
    sanitized = sanitize_value(value)
    text = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)
    if len(text) > MAX_SUMMARY_LENGTH:
        return text[:MAX_SUMMARY_LENGTH] + "...[truncated]"
    return text


def _tool_name_from_step(step: str) -> str | None:
    if "." in step or step.endswith("_tool"):
        return step
    return None


def build_trace_events_from_response(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert the in-memory tool_trace into persisted, sanitized trace events."""
    request_id = str(response.get("request_id") or "")
    session_id = str(response.get("session_id") or "")
    events: list[dict[str, Any]] = []
    created_at = _now_text()

    events.append(
        {
            "request_id": request_id,
            "session_id": session_id,
            "step_index": 1,
            "node_name": "receive_request",
            "action_type": "node_enter",
            "tool_name": None,
            "parameter_summary": _summary_text({"query_length": len(response.get("user_query", ""))}),
            "result_summary": _summary_text({"received": True}),
            "status": "success",
            "latency_ms": 0,
            "error_category": None,
            "retry_count": 0,
            "created_at": created_at,
        }
    )

    step_index = 2
    for trace_item in response.get("tool_trace", []):
        if not isinstance(trace_item, dict):
            continue
        step = str(trace_item.get("step") or "unknown_step")
        if step == "receive_request":
            continue
        tool_name = trace_item.get("tool_name") or _tool_name_from_step(step)
        action_type = "tool_result" if tool_name else "node_enter"
        if step in {"ticket_confirmation", "ask_for_order_id", "human_handoff", "unknown"}:
            action_type = "route_decision"
        if step == "format_response":
            action_type = "final_response"
        if trace_item.get("action_type"):
            action_type = str(trace_item["action_type"])
        events.append(
            {
                "request_id": request_id,
                "session_id": session_id,
                "step_index": step_index,
                "node_name": step,
                "action_type": action_type,
                "tool_name": tool_name,
                "parameter_summary": _summary_text(
                    {
                        key: value
                        for key, value in trace_item.items()
                        if key not in {"error", "latency_ms", "status"}
                    }
                ),
                "result_summary": _summary_text(trace_item),
                "status": str(trace_item.get("status") or "success"),
                "latency_ms": float(trace_item.get("latency_ms") or 0),
                "error_category": trace_item.get("error_type") or trace_item.get("error_category"),
                "retry_count": int(trace_item.get("retry_count") or 0),
                "created_at": created_at,
            }
        )
        step_index += 1

    events.append(
        {
            "request_id": request_id,
            "session_id": session_id,
            "step_index": step_index,
            "node_name": "final_response",
            "action_type": "final_response",
            "tool_name": None,
            "parameter_summary": _summary_text({"intent": response.get("intent")}),
            "result_summary": _summary_text(
                {
                    "answer_status": response.get("answer_status"),
                    "tool_used": response.get("tool_used"),
                    "confirmation_required": response.get("confirmation_required"),
                    "error_category": response.get("error_category"),
                    "retry_count": response.get("retry_count"),
                    "degraded": response.get("degraded"),
                    "fallback_action": response.get("fallback_action"),
                }
            ),
            "status": "success" if response.get("success", True) else "error",
            "latency_ms": 0,
            "error_category": response.get("error_category"),
            "retry_count": int(response.get("retry_count") or 0),
            "created_at": created_at,
        }
    )
    return events


def persist_trace_events(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    with _connect() as connection:
        connection.executemany(
            """
            INSERT INTO agent_trace_events (
                request_id,
                session_id,
                step_index,
                node_name,
                action_type,
                tool_name,
                parameter_summary,
                result_summary,
                status,
                latency_ms,
                error_category,
                retry_count,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event["request_id"],
                    event["session_id"],
                    event["step_index"],
                    event["node_name"],
                    event["action_type"],
                    event.get("tool_name"),
                    event["parameter_summary"],
                    event["result_summary"],
                    event["status"],
                    event["latency_ms"],
                    event.get("error_category"),
                    event["retry_count"],
                    event["created_at"],
                )
                for event in events
            ],
        )
        connection.commit()


def persist_response_trace(response: dict[str, Any]) -> list[dict[str, Any]]:
    events = build_trace_events_from_response(response)
    persist_trace_events(events)
    return events


def list_trace_events(request_id: str) -> list[dict[str, Any]]:
    cleaned_request_id = (request_id or "").strip()
    if not cleaned_request_id:
        return []
    with _connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                request_id,
                session_id,
                step_index,
                node_name,
                action_type,
                tool_name,
                parameter_summary,
                result_summary,
                status,
                latency_ms,
                error_category,
                retry_count,
                created_at
            FROM agent_trace_events
            WHERE request_id = ?
            ORDER BY step_index ASC, event_id ASC
            """,
            (cleaned_request_id,),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
