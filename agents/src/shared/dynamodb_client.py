"""DynamoDB persistence.

Single-table design, one item per fact about a claim:

    PK = CLAIM#{claim_id}
    SK = META            intake record and lifecycle status
    SK = AGENT#VISUAL    visual evidence agent output
    SK = AGENT#CLAIM     claim intelligence agent output
    SK = VERDICT         combined decision

Reads are a single Query on PK, so no secondary index is needed. Agents write
only their own item, which means two agents finishing simultaneously cannot
clobber each other.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from . import aws, config
from .errors import ConflictError, NotFoundError, ValidationError

logger = config.get_logger(__name__)

AGENT_VISUAL = "VISUAL"
AGENT_CLAIM = "CLAIM"

STATUS_PROCESSING = "processing"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"
STATUS_PENDING_REVIEW = "pending_human_review"

REVIEW_PENDING = "PENDING"
REVIEW_APPROVED_FRAUD = "APPROVED_FRAUD"
REVIEW_APPROVED_NOT_FRAUD = "APPROVED_NOT_FRAUD"
REVIEW_STATUSES = (REVIEW_PENDING, REVIEW_APPROVED_FRAUD, REVIEW_APPROVED_NOT_FRAUD)

HUMAN_DECISION_FRAUD = "FRAUD"
HUMAN_DECISION_NOT_FRAUD = "NOT_FRAUD"
HUMAN_DECISIONS = (HUMAN_DECISION_FRAUD, HUMAN_DECISION_NOT_FRAUD)

_AGENT_RESPONSE_KEYS = {AGENT_VISUAL: "visual", AGENT_CLAIM: "claim"}
_HUMAN_TO_REVIEW_STATUS = {
    HUMAN_DECISION_FRAUD: REVIEW_APPROVED_FRAUD,
    HUMAN_DECISION_NOT_FRAUD: REVIEW_APPROVED_NOT_FRAUD,
}


def _table() -> Any:
    return aws.dynamodb_table(config.table_name())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pk(claim_id: str) -> str:
    return f"CLAIM#{claim_id}"


def to_dynamo(value: Any) -> Any:
    """Convert floats to Decimal recursively; DynamoDB rejects Python floats.

    allow_nan=False makes NaN and Infinity fail here with a clear error rather
    than as an opaque serialisation failure inside boto3.
    """
    return json.loads(json.dumps(value, allow_nan=False), parse_float=Decimal)


def from_dynamo(value: Any) -> Any:
    """Convert Decimal back to int/float for JSON responses."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: from_dynamo(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [from_dynamo(inner) for inner in value]
    return value


def _with_ttl(item: Dict[str, Any]) -> Dict[str, Any]:
    days = config.claim_ttl_days()
    if days > 0:
        item["ttl"] = int(time.time()) + days * 86400
    return item


def create_claim(claim_id: str, intake: Dict[str, Any]) -> None:
    """Write the META item, refusing to overwrite an existing claim."""
    item = _with_ttl(
        {
            "PK": _pk(claim_id),
            "SK": "META",
            "claim_id": claim_id,
            "status": STATUS_PROCESSING,
            "created_at": _now(),
            "updated_at": _now(),
            **to_dynamo(intake),
        }
    )
    try:
        _table().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise ConflictError(f"Claim {claim_id} already exists") from exc
        raise
    logger.info("Created claim %s", claim_id)


def set_claim_status(claim_id: str, status: str, **extra: Any) -> None:
    names = {"#status": "status", "#updated_at": "updated_at"}
    values: Dict[str, Any] = {":status": status, ":updated_at": _now()}
    assignments = ["#status = :status", "#updated_at = :updated_at"]

    for index, (field, value) in enumerate(extra.items()):
        names[f"#f{index}"] = field
        values[f":v{index}"] = to_dynamo(value)
        assignments.append(f"#f{index} = :v{index}")

    _table().update_item(
        Key={"PK": _pk(claim_id), "SK": "META"},
        UpdateExpression="SET " + ", ".join(assignments),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def save_agent_result(claim_id: str, agent: str, result: Dict[str, Any]) -> None:
    _table().put_item(
        Item=_with_ttl(
            {
                "PK": _pk(claim_id),
                "SK": f"AGENT#{agent}",
                "claim_id": claim_id,
                "agent": agent,
                "status": "ok",
                "result": to_dynamo(result),
                "analyzed_at": _now(),
            }
        )
    )
    logger.info("Saved %s result for claim %s", agent, claim_id)


def save_agent_failure(claim_id: str, agent: str, message: str) -> None:
    _table().put_item(
        Item=_with_ttl(
            {
                "PK": _pk(claim_id),
                "SK": f"AGENT#{agent}",
                "claim_id": claim_id,
                "agent": agent,
                "status": "failed",
                "error": message[:1000],
                "analyzed_at": _now(),
            }
        )
    )
    logger.warning("Recorded %s failure for claim %s: %s", agent, claim_id, message)


def save_verdict(claim_id: str, verdict: Dict[str, Any]) -> None:
    _table().put_item(
        Item=_with_ttl(
            {
                "PK": _pk(claim_id),
                "SK": "VERDICT",
                "claim_id": claim_id,
                "verdict": to_dynamo(verdict),
                "decided_at": _now(),
            }
        )
    )


def get_claim(claim_id: str) -> Optional[Dict[str, Any]]:
    """Assemble the full public view of a claim, or None if it does not exist."""
    items = []
    query: Dict[str, Any] = {
        "KeyConditionExpression": Key("PK").eq(_pk(claim_id)),
        "ConsistentRead": True,
    }
    while True:
        page = _table().query(**query)
        items.extend(page.get("Items", []))
        token = page.get("LastEvaluatedKey")
        if not token:
            break
        query["ExclusiveStartKey"] = token

    if not items:
        return None

    meta: Optional[Dict[str, Any]] = None
    agents: Dict[str, Any] = {"visual": None, "claim": None}
    verdict: Optional[Dict[str, Any]] = None
    review: Optional[Dict[str, Any]] = None

    for item in items:
        sort_key = item.get("SK", "")
        if sort_key == "META":
            meta = item
        elif sort_key == "VERDICT":
            verdict = from_dynamo(item.get("verdict"))
        elif sort_key == "REVIEW":
            review = _public_review(item)
        elif sort_key.startswith("AGENT#"):
            response_key = _AGENT_RESPONSE_KEYS.get(sort_key.split("#", 1)[1])
            if response_key:
                agents[response_key] = {
                    "status": item.get("status"),
                    "result": from_dynamo(item.get("result")),
                    "error": item.get("error"),
                    "analyzed_at": item.get("analyzed_at"),
                }

    if meta is None:
        # Agent items exist without a META item, which should not happen.
        return None

    body: Dict[str, Any] = {
        "claim_id": claim_id,
        "status": meta.get("status", STATUS_PROCESSING),
        "product_category": meta.get("product_category"),
        "order_value_usd": from_dynamo(meta.get("order_value_usd")),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "human_decision": meta.get("human_decision"),
        "agents": agents,
        "verdict": verdict,
        "review": review,
    }
    if verdict:
        body["decision"] = verdict.get("decision")
        body["confidence"] = verdict.get("confidence")
        body["reason"] = verdict.get("reason")
        body["requires_human_review"] = verdict.get("requires_human_review")
    if review and review.get("human_decision"):
        body["decision"] = review["human_decision"]
        body["requires_human_review"] = False
        body["reviewed_at"] = review.get("reviewed_at")
    return body


def _public_review(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "case_id": item.get("case_id") or item.get("claim_id"),
        "message": item.get("message"),
        "s3_url": item.get("s3_url"),
        "agent_1_result": from_dynamo(item.get("agent_1_result")),
        "agent_3_result": from_dynamo(item.get("agent_3_result")),
        "agent_6_result": from_dynamo(item.get("agent_6_result")),
        "confidence": from_dynamo(item.get("confidence")),
        "status": item.get("review_status") or item.get("status"),
        "created_at": item.get("created_at"),
        "human_decision": item.get("human_decision"),
        "reviewed_at": item.get("reviewed_at"),
        "reason": item.get("reason"),
    }


def get_review(case_id: str) -> Optional[Dict[str, Any]]:
    reply = _table().get_item(Key={"PK": _pk(case_id), "SK": "REVIEW"}, ConsistentRead=True)
    item = reply.get("Item")
    if not item:
        return None
    return _public_review(item)


def save_pending_review(
    case_id: str,
    *,
    message: str,
    s3_url: str,
    agent_1_result: Any,
    agent_3_result: Any,
    agent_6_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a PENDING review row. Idempotent if the same case is already pending."""
    existing = get_review(case_id)
    if existing is not None:
        if existing.get("status") == REVIEW_PENDING:
            logger.info("Review for %s already pending; not duplicating", case_id)
            return existing
        raise ConflictError(f"Case {case_id} already has a review in status {existing.get('status')}")

    now = _now()
    item = _with_ttl(
        {
            "PK": _pk(case_id),
            "SK": "REVIEW",
            "case_id": case_id,
            "claim_id": case_id,
            "message": message,
            "s3_url": s3_url,
            "agent_1_result": to_dynamo(agent_1_result),
            "agent_3_result": to_dynamo(agent_3_result),
            "agent_6_result": to_dynamo(agent_6_result),
            "confidence": to_dynamo(agent_6_result.get("confidence")),
            "reason": agent_6_result.get("reason") or "",
            "review_status": REVIEW_PENDING,
            "status": REVIEW_PENDING,
            "created_at": now,
            "human_decision": None,
            "reviewed_at": None,
        }
    )
    try:
        _table().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            existing = get_review(case_id)
            if existing and existing.get("status") == REVIEW_PENDING:
                return existing
            raise ConflictError(f"Review for case {case_id} already exists") from exc
        raise
    logger.info("Created pending review for case %s", case_id)
    return _public_review(item)


def list_pending_reviews(limit: int = 50) -> List[Dict[str, Any]]:
    """Newest pending human-review cases first."""
    cap = max(1, min(100, int(limit)))
    items: List[Dict[str, Any]] = []
    query: Dict[str, Any] = {
        "IndexName": config.review_index_name(),
        "KeyConditionExpression": Key("review_status").eq(REVIEW_PENDING),
        "ScanIndexForward": False,
        "Limit": cap,
    }
    while len(items) < cap:
        page = _table().query(**query)
        items.extend(page.get("Items", []))
        token = page.get("LastEvaluatedKey")
        if not token:
            break
        query["ExclusiveStartKey"] = token
        query["Limit"] = cap - len(items)
    return [_public_review(item) for item in items[:cap]]


def apply_human_decision(case_id: str, decision: str) -> Dict[str, Any]:
    """Record an admin FRAUD / NOT_FRAUD decision on a PENDING review."""
    normalized = str(decision or "").strip().upper().replace("-", "_")
    if normalized in ("APPROVED_FRAUD", "APPROVE_FRAUD"):
        normalized = HUMAN_DECISION_FRAUD
    if normalized in ("APPROVED_NOT_FRAUD", "APPROVE_NOT_FRAUD", "NOTFRAUD"):
        normalized = HUMAN_DECISION_NOT_FRAUD
    if normalized not in HUMAN_DECISIONS:
        raise ValidationError("decision must be FRAUD or NOT_FRAUD")

    current = get_review(case_id)
    if current is None:
        raise NotFoundError(f"No review found for case {case_id}")
    if current.get("status") != REVIEW_PENDING:
        raise ConflictError(
            f"Case {case_id} is already decided ({current.get('status')})"
        )

    review_status = _HUMAN_TO_REVIEW_STATUS[normalized]
    reviewed_at = _now()
    try:
        _table().update_item(
            Key={"PK": _pk(case_id), "SK": "REVIEW"},
            UpdateExpression=(
                "SET review_status = :rs, #status = :rs, human_decision = :hd, "
                "reviewed_at = :ts"
            ),
            ConditionExpression="review_status = :pending",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":rs": review_status,
                ":hd": normalized,
                ":ts": reviewed_at,
                ":pending": REVIEW_PENDING,
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise ConflictError(f"Case {case_id} is no longer pending review") from exc
        raise

    set_claim_status(
        case_id,
        STATUS_COMPLETE,
        human_decision=normalized,
        reviewed_at=reviewed_at,
    )
    logger.info("Human decided %s for case %s", normalized, case_id)
    updated = get_review(case_id) or current
    updated["human_decision"] = normalized
    updated["status"] = review_status
    updated["reviewed_at"] = reviewed_at
    return updated
