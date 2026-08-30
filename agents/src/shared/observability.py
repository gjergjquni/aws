"""Structured invocation logging without secrets or raw customer content."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

_REDACT_KEYS = {
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "api_key",
    "authorization",
    "secret",
    "secret_key",
    "access_key_id",
    "access_key",
    "password",
    "customer_text",
    "claimed_condition",
    "customer_claimed_condition",
}


def _strip_signed_url(value: str) -> str:
    """Never log presigned query strings."""
    lowered = value.lower()
    if "x-amz-" in lowered or "signature=" in lowered or "?" in value and "amazonaws.com" in lowered:
        return value.split("?", 1)[0]
    return value


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in _REDACT_KEYS else _safe(inner)
            for key, inner in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, str):
        return _strip_signed_url(value)
    return value


def log_event(logger: Any, **fields: Any) -> None:
    payload = {key: value for key, value in fields.items() if value is not None}
    logger.info("aegis_event %s", json.dumps(_safe(payload), default=str, separators=(",", ":")))


@contextmanager
def invocation(
    logger: Any,
    *,
    agent_name: str,
    claim_id: str,
    request_id: Optional[str] = None,
) -> Iterator[Dict[str, Any]]:
    started = time.perf_counter()
    state: Dict[str, Any] = {
        "agent_name": agent_name,
        "claim_id": claim_id,
        "request_id": request_id,
        "execution_status": "started",
    }
    log_event(logger, **state)
    try:
        yield state
        state.setdefault("execution_status", "ok")
    except Exception as exc:
        state["execution_status"] = "failed"
        state["error_type"] = type(exc).__name__
        raise
    finally:
        state["latency_ms"] = int((time.perf_counter() - started) * 1000)
        log_event(logger, **state)


def aws_failure(logger: Any, *, service: str, operation: str, error: str, claim_id: str = "") -> None:
    log_event(
        logger,
        event="aws_service_failure",
        service=service,
        operation=operation,
        error=error[:300],
        claim_id=claim_id or None,
    )
