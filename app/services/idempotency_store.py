"""SQLite-backed idempotency records for simulated ticket creation."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any
from uuid import uuid4

import app.tools.order_tool as order_tool_module


IDEMPOTENCY_STATUS_PENDING = "pending"
IDEMPOTENCY_STATUS_COMPLETED = "completed"
IDEMPOTENCY_STATUS_FAILED = "failed"


def _now_text() -> str:
    return datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def generate_idempotency_key() -> str:
    return f"idem_{uuid4().hex}"


def _connect() -> sqlite3.Connection:
    database_path = order_tool_module.get_database_path()
    order_tool_module.ensure_database_exists(database_path)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    ensure_idempotency_table(connection)
    return connection


def ensure_idempotency_table(connection: sqlite3.Connection | None = None) -> None:
    """Create idempotency table with a database-level unique key."""
    owns_connection = connection is None
    active_connection = connection or sqlite3.connect(order_tool_module.get_database_path())
    try:
        active_connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_idempotency_records (
                idempotency_key TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                order_id TEXT,
                ticket_id INTEGER,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        active_connection.commit()
    finally:
        if owns_connection:
            active_connection.close()


def _row_to_record(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def get_idempotency_record(idempotency_key: str) -> dict[str, Any] | None:
    cleaned_key = (idempotency_key or "").strip()
    if not cleaned_key:
        return None
    with _connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                idempotency_key,
                session_id,
                action_type,
                order_id,
                ticket_id,
                status,
                created_at,
                updated_at
            FROM ticket_idempotency_records
            WHERE idempotency_key = ?
            """,
            (cleaned_key,),
        )
        return _row_to_record(cursor.fetchone())


def create_or_get_pending_record(
    idempotency_key: str,
    session_id: str,
    action_type: str,
    order_id: str | None,
) -> dict[str, Any]:
    """Insert a pending idempotency record, or return the existing row."""
    now = _now_text()
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO ticket_idempotency_records (
                idempotency_key,
                session_id,
                action_type,
                order_id,
                ticket_id,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                idempotency_key,
                session_id,
                action_type,
                order_id,
                IDEMPOTENCY_STATUS_PENDING,
                now,
                now,
            ),
        )
        connection.commit()
    record = get_idempotency_record(idempotency_key)
    if record is None:
        raise RuntimeError("idempotency record insert/read failed")
    return record


def complete_idempotency_record(idempotency_key: str, ticket_id: int) -> dict[str, Any]:
    now = _now_text()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE ticket_idempotency_records
            SET ticket_id = ?, status = ?, updated_at = ?
            WHERE idempotency_key = ?
            """,
            (ticket_id, IDEMPOTENCY_STATUS_COMPLETED, now, idempotency_key),
        )
        connection.commit()
    record = get_idempotency_record(idempotency_key)
    if record is None:
        raise RuntimeError("idempotency record update/read failed")
    return record
