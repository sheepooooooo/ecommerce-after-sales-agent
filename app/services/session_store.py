"""
SQLite-backed conversation session state for multi-turn confirmation.

This module is not an Agent tool. It stores pending user-confirmed actions so a
second request with the same session_id can continue the previous turn safely.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any
from uuid import uuid4

import app.tools.order_tool as order_tool_module


SESSION_STATUS_IDLE = "idle"
SESSION_STATUS_PENDING = "pending_confirmation"
SESSION_STATUS_AWAITING_ORDER_ID = "awaiting_order_id"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_CANCELLED = "cancelled"
SESSION_STATUS_INTERRUPTED = "interrupted"


def _now_text() -> str:
    return datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _connect() -> sqlite3.Connection:
    database_path = order_tool_module.get_database_path()
    order_tool_module.ensure_database_exists(database_path)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    ensure_session_table(connection)
    return connection


def ensure_session_table(connection: sqlite3.Connection | None = None) -> None:
    """
    Ensure the session table exists.

    Older local databases may not have this table yet, so runtime callers create
    it idempotently instead of requiring a destructive re-init.
    """
    owns_connection = connection is None
    active_connection = connection or sqlite3.connect(order_tool_module.get_database_path())
    try:
        active_connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                session_id TEXT PRIMARY KEY,
                pending_action TEXT,
                pending_order_id TEXT,
                pending_payload TEXT NOT NULL DEFAULT '{}',
                pending_reason TEXT,
                workflow_type TEXT,
                conversation_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        existing_columns = {
            row[1]
            for row in active_connection.execute("PRAGMA table_info(conversation_sessions)").fetchall()
        }
        if "pending_reason" not in existing_columns:
            active_connection.execute("ALTER TABLE conversation_sessions ADD COLUMN pending_reason TEXT")
        if "workflow_type" not in existing_columns:
            active_connection.execute("ALTER TABLE conversation_sessions ADD COLUMN workflow_type TEXT")
        active_connection.commit()
    finally:
        if owns_connection:
            active_connection.close()


def _row_to_session(row: sqlite3.Row) -> dict[str, Any]:
    payload_text = row["pending_payload"] or "{}"
    try:
        pending_payload = json.loads(payload_text)
    except json.JSONDecodeError:
        pending_payload = {}
    return {
        "session_id": row["session_id"],
        "pending_action": row["pending_action"],
        "pending_order_id": row["pending_order_id"],
        "pending_payload": pending_payload,
        "pending_reason": row["pending_reason"],
        "workflow_type": row["workflow_type"],
        "conversation_status": row["conversation_status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_or_create_session(session_id: str | None = None) -> dict[str, Any]:
    actual_session_id = (session_id or "").strip() or str(uuid4())
    with _connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                session_id,
                pending_action,
                pending_order_id,
                pending_payload,
                pending_reason,
                workflow_type,
                conversation_status,
                created_at,
                updated_at
            FROM conversation_sessions
            WHERE session_id = ?
            """,
            (actual_session_id,),
        )
        row = cursor.fetchone()
        if row is not None:
            return _row_to_session(row)

        now = _now_text()
        cursor.execute(
            """
            INSERT INTO conversation_sessions (
                session_id,
                pending_action,
                pending_order_id,
                pending_payload,
                pending_reason,
                workflow_type,
                conversation_status,
                created_at,
                updated_at
            )
            VALUES (?, NULL, NULL, '{}', NULL, NULL, ?, ?, ?)
            """,
            (actual_session_id, SESSION_STATUS_IDLE, now, now),
        )
        connection.commit()
    return get_or_create_session(actual_session_id)


def get_session(session_id: str) -> dict[str, Any] | None:
    cleaned_session_id = (session_id or "").strip()
    if not cleaned_session_id:
        return None
    with _connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                session_id,
                pending_action,
                pending_order_id,
                pending_payload,
                pending_reason,
                workflow_type,
                conversation_status,
                created_at,
                updated_at
            FROM conversation_sessions
            WHERE session_id = ?
            """,
            (cleaned_session_id,),
        )
        row = cursor.fetchone()
    return _row_to_session(row) if row else None


def save_pending_action(
    session_id: str,
    pending_action: str,
    pending_order_id: str | None,
    pending_payload: dict[str, Any],
    pending_reason: str | None = None,
    workflow_type: str | None = None,
    conversation_status: str = SESSION_STATUS_PENDING,
) -> dict[str, Any]:
    now = _now_text()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE conversation_sessions
            SET
                pending_action = ?,
                pending_order_id = ?,
                pending_payload = ?,
                pending_reason = ?,
                workflow_type = ?,
                conversation_status = ?,
                updated_at = ?
            WHERE session_id = ?
            """,
            (
                pending_action,
                pending_order_id,
                json.dumps(pending_payload, ensure_ascii=False),
                pending_reason,
                workflow_type,
                conversation_status,
                now,
                session_id,
            ),
        )
        connection.commit()
    return get_or_create_session(session_id)


def clear_pending_action(session_id: str, conversation_status: str = SESSION_STATUS_IDLE) -> dict[str, Any]:
    now = _now_text()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE conversation_sessions
            SET
                pending_action = NULL,
                pending_order_id = NULL,
                pending_payload = '{}',
                pending_reason = NULL,
                workflow_type = NULL,
                conversation_status = ?,
                updated_at = ?
            WHERE session_id = ?
            """,
            (conversation_status, now, session_id),
        )
        connection.commit()
    return get_or_create_session(session_id)


def mark_pending_action_completed(session_id: str, completed_payload: dict[str, Any]) -> dict[str, Any]:
    """Keep the completed action summary so repeated confirmation can return safely."""
    now = _now_text()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE conversation_sessions
            SET
                pending_action = NULL,
                pending_order_id = NULL,
                pending_payload = ?,
                pending_reason = NULL,
                workflow_type = NULL,
                conversation_status = ?,
                updated_at = ?
            WHERE session_id = ?
            """,
            (
                json.dumps(completed_payload, ensure_ascii=False),
                SESSION_STATUS_COMPLETED,
                now,
                session_id,
            ),
        )
        connection.commit()
    return get_or_create_session(session_id)


def has_pending_action(session: dict[str, Any] | None, pending_action: str | None = None) -> bool:
    if not session:
        return False
    if session.get("conversation_status") not in {SESSION_STATUS_PENDING, SESSION_STATUS_AWAITING_ORDER_ID}:
        return False
    if not session.get("pending_action"):
        return False
    if pending_action is not None and session.get("pending_action") != pending_action:
        return False
    return True
