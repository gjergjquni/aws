"""POST /analyze and GET /analyze/{caseId}.

POST starts Agent 1 and Agent 3 in parallel (Step Functions) and returns a
case id the frontend can poll. GET returns the frontend-facing Agent 6
decision once the workflow finishes — either an automatic FRAUD / NOT_FRAUD
result or pending_human_review.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError

from shared import aws, config, dynamodb_client, evidence, http, observability, s3_utils
from shared.errors import NotFoundError, ValidationError

logger = config.get_logger(__name__)

MAX_CATEGORY_CHARS = 60
MAX_CONDITION_CHARS = 2000
MAX_ORDER_VALUE = 1_000_000.0


def _text_alias(payload: Dict[str, Any], *names: str) -> Optional[str]:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _order_value(raw: Any) -> float:
    if raw is None or raw == "":
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError("order_value_usd must be a number") from exc
    if value != value or value in (float("inf"), float("-inf")):
        raise ValidationError("order_value_usd must be a finite number")
    if value < 0:
        raise ValidationError("order_value_usd cannot be negative")
    if value > MAX_ORDER_VALUE:
        raise ValidationError(f"order_value_usd cannot exceed {MAX_ORDER_VALUE:.0f}")
    return round(value, 2)


def _category(payload: Dict[str, Any]) -> str:
    raw = payload.get("product_category")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return "other"
    if not isinstance(raw, str):
        raise ValidationError("product_category must be a string")
    category = " ".join(raw.strip().lower().split())
    if len(category) > MAX_CATEGORY_CHARS:
        raise ValidationError(f"product_category cannot exceed {MAX_CATEGORY_CHARS} characters")
    return category


def _start_execution(claim_id: str, execution_input: Dict[str, Any]) -> str:
    client = aws.client("stepfunctions", read_timeout=10)
    try:
        started = client.start_execution(
            stateMachineArn=config.state_machine_arn(),
            name=claim_id,
            input=json.dumps(execution_input),
        )
        return started["executionArn"]
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ExecutionAlreadyExists":
            logger.info("Workflow for case %s already running; treating as idempotent", claim_id)
            return ""
        raise


def _public_from_claim(claim: Dict[str, Any]) -> Dict[str, Any]:
    status = claim.get("status")
    case_id = claim.get("claim_id")
    if status == dynamodb_client.STATUS_PROCESSING:
        return {
            "status": "processing",
            "case_id": case_id,
            "message": "Analysis is still running. Poll this endpoint until status is completed or pending_human_review.",
            "poll_url": f"/analyze/{case_id}",
        }
    if status == dynamodb_client.STATUS_FAILED:
        return {
            "status": "failed",
            "case_id": case_id,
            "decision": None,
            "reason": claim.get("note") or (claim.get("verdict") or {}).get("reason") or "Analysis failed",
            "message": "The fraud analysis failed. See reason for details.",
        }
    if status == dynamodb_client.STATUS_PENDING_REVIEW:
        return {
            "status": "pending_human_review",
            "case_id": case_id,
            "decision": "HUMAN_REVIEW",
            "confidence": claim.get("confidence"),
            "reason": claim.get("reason") or "",
            "requires_human_review": True,
            "message": "This case requires human review.",
        }
    # complete — may already include a human decision
    human = (claim.get("review") or {}).get("human_decision")
    decision = human or claim.get("decision")
    return {
        "status": "completed",
        "case_id": case_id,
        "decision": decision,
        "confidence": claim.get("confidence"),
        "reason": claim.get("reason") or "",
        "requires_human_review": False,
        "human_decision": human,
    }


def _post_analyze(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = http.parse_json_body(event)

    message = _text_alias(payload, "message", "customer_text")
    if not message:
        raise ValidationError("Missing required field: message")
    if len(message) > config.max_customer_text_chars():
        raise ValidationError(
            f"message cannot exceed {config.max_customer_text_chars()} characters"
        )

    raw_id = payload.get("case_id") or payload.get("claim_id")
    if raw_id:
        claim_id = http.validate_claim_id(raw_id)
    else:
        claim_id = http.new_case_id()

    observability.log_event(logger, event="EVIDENCE_RECEIVED", claim_id=claim_id)
    evidence_items = evidence.from_payload(payload, required=True, field="s3_url")
    s3_key = evidence_items[0]["key"]
    all_keys = [item["key"] for item in evidence_items]

    condition = _text_alias(payload, "customer_claimed_condition") or message[:MAX_CONDITION_CHARS]
    if len(condition) > MAX_CONDITION_CHARS:
        raise ValidationError(f"customer_claimed_condition cannot exceed {MAX_CONDITION_CHARS} characters")
    product_category = _category(payload)
    order_value_usd = _order_value(payload.get("order_value_usd"))

    size_bytes = 0
    for item in evidence_items:
        size_bytes += s3_utils.assert_object_exists(item["key"])

    s3_url = evidence.canonical_uri(evidence_items[0])
    dynamodb_client.create_claim(
        claim_id,
        {
            "s3_key": s3_key,
            "s3_keys": all_keys,
            "s3_url": s3_url,
            "evidence": evidence_items[0],
            "evidence_bytes": size_bytes,
            "product_category": product_category,
            "customer_claimed_condition": condition,
            "customer_text": message,
            "message": message,
            "order_value_usd": order_value_usd,
        },
    )

    execution_arn = _start_execution(
        claim_id,
        evidence.workflow_payload(
            claim_id=claim_id,
            evidence_items=evidence_items,
            product_category=product_category,
            customer_claimed_condition=condition,
            customer_text=message,
            order_value_usd=order_value_usd,
        ),
    )
    logger.info("Accepted analyze case %s (execution %s)", claim_id, execution_arn or "existing")
    return http.response(
        202,
        {
            "status": "processing",
            "case_id": claim_id,
            "poll_url": f"/analyze/{claim_id}",
            "message": (
                "Agent 1 and Agent 3 are running in parallel. Poll poll_url until "
                "status is completed or pending_human_review."
            ),
        },
    )


def _get_analyze(event: Dict[str, Any]) -> Dict[str, Any]:
    case_id = http.path_id(event, "caseId", "claimId")
    claim = dynamodb_client.get_claim(case_id)
    if claim is None:
        raise NotFoundError(f"No case found with id {case_id}")
    return http.response(200, _public_from_claim(claim))


@http.api_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    method = str(event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method") or "POST").upper()
    if method == "GET":
        return _get_analyze(event)
    return _post_analyze(event)
