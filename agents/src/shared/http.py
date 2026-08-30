"""API Gateway proxy request/response helpers.

Error bodies use a single shape so the frontend can branch on a stable code
instead of parsing prose:

    {"error": {"code": "validation_error", "message": "..."}}
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict
from uuid import uuid4

from . import config
from .errors import (
    AegisError,
    ConfigError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

logger = config.get_logger(__name__)

# Safe as an S3 key segment and as a Step Functions execution name.
CLAIM_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")


class _DecimalEncoder(json.JSONEncoder):
    """DynamoDB hands back Decimal; JSON has no such type."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        return super().default(o)


def cors_headers() -> Dict[str, str]:
    origin = config.allowed_origin()
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "Content-Type,x-api-key",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Cache-Control": "no-store",
    }
    if origin != "*":
        # Required for caches and CDNs to key responses per origin.
        headers["Vary"] = "Origin"
    return headers


def response(status_code: int, body: Any) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": cors_headers(),
        "body": json.dumps(body, cls=_DecimalEncoder),
    }


def error(status_code: int, code: str, message: str) -> Dict[str, Any]:
    return response(status_code, {"error": {"code": code, "message": message}})


def parse_json_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return the request body as a dict, or raise ValidationError."""
    raw = event.get("body")
    if raw is None or raw == "":
        raise ValidationError("Request body is required")
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValidationError("Request body must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValidationError("Request body must be a JSON object")
    return parsed


def require_field(payload: Dict[str, Any], name: str) -> Any:
    value = payload.get(name)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"Missing required field: {name}")
    return value


def validate_claim_id(value: Any) -> str:
    claim_id = value.strip() if isinstance(value, str) else ""
    if not CLAIM_ID_PATTERN.match(claim_id):
        raise ValidationError(
            "claim_id must be 3-64 characters of letters, digits, hyphens or underscores"
        )
    return claim_id


def new_case_id() -> str:
    """Mint an id for POST /analyze when the caller does not supply one."""
    return f"CASE-{uuid4().hex[:12].upper()}"


def path_id(event: Dict[str, Any], *names: str) -> str:
    params = event.get("pathParameters") or {}
    for name in names:
        raw = params.get(name)
        if raw:
            return validate_claim_id(raw)
    raise ValidationError(f"Missing required path parameter: {names[0] if names else 'id'}")


def api_handler(func: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
    """Translate exceptions into proxy responses with the right status code.

    Unexpected exceptions log a full traceback but return a generic message, so
    internal detail (bucket names, ARNs, stack frames) never reaches the client.
    """

    def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        try:
            return func(event, context)
        except ValidationError as exc:
            return error(400, getattr(exc, "code", None) or ValidationError.code, str(exc))
        except NotFoundError as exc:
            return error(404, NotFoundError.code, str(exc))
        except ConflictError as exc:
            return error(409, ConflictError.code, str(exc))
        except ConfigError:
            logger.exception("Configuration error")
            return error(500, "misconfigured", "The service is misconfigured")
        except AegisError:
            logger.exception("Request failed")
            return error(502, "upstream_error", "A dependency failed to respond")
        except Exception:
            logger.exception("Unhandled error")
            return error(500, "internal_error", "An unexpected error occurred")

    wrapper.__name__ = getattr(func, "__name__", "handler")
    return wrapper
