"""Finite retry helper for read-only technical failures."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from app.config import get_retry_config
from app.services.error_taxonomy import classify_exception, is_retryable_category
from app.services.trace_store import sanitize_value


T = TypeVar("T")


class RetryExhaustedError(Exception):
    """Raised after all retryable attempts are exhausted."""

    def __init__(
        self,
        message: str,
        error_category: str,
        retry_count: int,
        trace_events: list[dict[str, Any]],
    ) -> None:
        super().__init__(message)
        self.error_category = error_category
        self.retry_count = retry_count
        self.trace_events = trace_events


def execute_with_retry(
    operation_name: str,
    func: Callable[[], T],
    *,
    sleep_func: Callable[[float], None] | None = None,
    retry_config: dict[str, Any] | None = None,
) -> tuple[T, dict[str, Any]]:
    """Run a read-only operation with bounded retries and trace summaries."""
    config = retry_config or get_retry_config()
    max_retries = int(config["max_retries"])
    base_delay = float(config["base_delay_seconds"])
    backoff_multiplier = float(config["backoff_multiplier"])
    sleeper = sleep_func or time.sleep
    trace_events: list[dict[str, Any]] = []
    attempt_index = 0
    retry_count = 0

    while True:
        start = time.perf_counter()
        try:
            result = func()
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            if retry_count:
                trace_events.append(
                    {
                        "step": operation_name,
                        "action_type": "retry_success",
                        "status": "success",
                        "latency_ms": latency_ms,
                        "retry_count": retry_count,
                    }
                )
            return result, {"retry_count": retry_count, "trace_events": trace_events}
        except Exception as error:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            error_category = classify_exception(error)
            sanitized_error = sanitize_value(str(error))
            if not is_retryable_category(error_category):
                raise
            if retry_count >= max_retries:
                trace_events.append(
                    {
                        "step": operation_name,
                        "action_type": "retry_exhausted",
                        "status": "error",
                        "latency_ms": latency_ms,
                        "retry_count": retry_count,
                        "error_category": error_category,
                        "error_summary": sanitized_error,
                    }
                )
                raise RetryExhaustedError(
                    message=f"{operation_name} retry exhausted",
                    error_category=error_category,
                    retry_count=retry_count,
                    trace_events=trace_events,
                ) from error

            retry_count += 1
            trace_events.append(
                {
                    "step": operation_name,
                    "action_type": "retry_attempt",
                    "status": "error",
                    "latency_ms": latency_ms,
                    "retry_count": retry_count,
                    "error_category": error_category,
                    "error_summary": sanitized_error,
                }
            )
            delay_seconds = base_delay * (backoff_multiplier ** attempt_index)
            attempt_index += 1
            if delay_seconds > 0:
                sleeper(delay_seconds)
