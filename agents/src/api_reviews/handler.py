"""Admin human-review APIs.

GET  /reviews/pending
POST /reviews/{caseId}/decision   { "decision": "FRAUD" | "NOT_FRAUD" }
GET  /reviews/{caseId}
"""

from __future__ import annotations

from typing import Any, Dict

from shared import config, dynamodb_client, http
from shared.errors import NotFoundError, ValidationError

logger = config.get_logger(__name__)


def _limit(event: Dict[str, Any]) -> int:
    params = event.get("queryStringParameters") or {}
    raw = params.get("limit") if isinstance(params, dict) else None
    if raw is None or raw == "":
        return 50
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError("limit must be an integer") from exc


def _pending(_event: Dict[str, Any]) -> Dict[str, Any]:
    cases = dynamodb_client.list_pending_reviews(limit=_limit(_event))
    return http.response(
        200,
        {
            "status": "ok",
            "count": len(cases),
            "cases": cases,
        },
    )


def _get_one(event: Dict[str, Any]) -> Dict[str, Any]:
    case_id = http.path_id(event, "caseId", "claimId")
    review = dynamodb_client.get_review(case_id)
    if review is None:
        raise NotFoundError(f"No review found for case {case_id}")
    return http.response(200, review)


def _decide(event: Dict[str, Any]) -> Dict[str, Any]:
    case_id = http.path_id(event, "caseId", "claimId")
    payload = http.parse_json_body(event)
    decision = http.require_field(payload, "decision")
    if not isinstance(decision, str):
        raise ValidationError("decision must be a string")
    updated = dynamodb_client.apply_human_decision(case_id, decision)
    return http.response(
        200,
        {
            "status": "completed",
            "case_id": case_id,
            "decision": updated.get("human_decision"),
            "review_status": updated.get("status"),
            "reviewed_at": updated.get("reviewed_at"),
            "reason": updated.get("reason"),
        },
    )


@http.api_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    method = str(event.get("httpMethod") or "").upper()
    path = str(event.get("path") or event.get("resource") or "")
    params = event.get("pathParameters") or {}

    if method == "GET":
        case = str(params.get("caseId") or params.get("claimId") or "")
        if not case or case.lower() == "pending":
            return _pending(event)
        return _get_one(event)
    if method == "POST" and ("/decision" in path or params.get("caseId") or params.get("claimId")):
        return _decide(event)
    raise ValidationError("Unsupported reviews request")
