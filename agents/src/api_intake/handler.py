"""POST /claims — validate a submitted claim and start the analysis workflow.

Called by the upload service once the evidence photo is already in S3. The
claim_id is supplied by the caller (their order or claim reference), not minted
here, so their system stays the source of truth for identity.

``s3_image_url`` is whatever form the upload service names the object in — an
``s3://`` URI, an HTTPS endpoint URL, a presigned URL, or a bare key. It is
resolved to an object key once here, so the agents downstream only ever see a key
that has already been checked against the configured bucket and prefix.

Returns 202 immediately; both agents run asynchronously in Step Functions and the
caller polls GET /results/{claimId}. The execution is named after the claim, so
resubmitting the same claim_id is idempotent rather than double-billing two
Bedrock runs.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from botocore.exceptions import ClientError

from shared import aws, config, dynamodb_client, evidence, http, observability, s3_utils
from shared.errors import ValidationError

logger = config.get_logger(__name__)

MAX_CATEGORY_CHARS = 60
MAX_CONDITION_CHARS = 2000
MAX_ORDER_VALUE = 1_000_000.0


def _product_category(payload: Dict[str, Any]) -> str:
    """Normalise the category without restricting it to the canonical three.

    The frontend contract publishes electronics|clothing|other, but a category
    outside that set is accepted rather than rejected. Two reasons: a new product
    line must never be able to fail a fraud check, and the real category name is
    better prompt context than "other" ("does this damage make sense for hiking
    boots" beats "does this damage make sense for other").

    An unrecognised value is logged so it shows up in CloudWatch during
    integration, which is how the canonical list gets extended on purpose instead
    of drifting silently.
    """
    raw = http.require_field(payload, "product_category")
    if not isinstance(raw, str):
        raise ValidationError("product_category must be a string")
    category = " ".join(raw.strip().lower().split())
    if len(category) > MAX_CATEGORY_CHARS:
        raise ValidationError(f"product_category cannot exceed {MAX_CATEGORY_CHARS} characters")
    if category not in config.PRODUCT_CATEGORIES:
        logger.info(
            "product_category %r is outside the published set %s; accepting it",
            category,
            "|".join(config.PRODUCT_CATEGORIES),
        )
    return category


def _order_value(raw: Any) -> float:
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


def _bounded_text(payload: Dict[str, Any], field: str, limit: int) -> str:
    value = http.require_field(payload, field)
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    text = value.strip()
    if len(text) > limit:
        raise ValidationError(f"{field} cannot exceed {limit} characters")
    return text


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
            logger.info("Workflow for claim %s already running; treating as idempotent", claim_id)
            return ""
        raise


@http.api_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    payload = http.parse_json_body(event)

    claim_id = http.validate_claim_id(http.require_field(payload, "claim_id"))
    observability.log_event(logger, event="EVIDENCE_RECEIVED", claim_id=claim_id)
    evidence_items = evidence.from_payload(payload, required=True, field="s3_image_url")
    s3_key = evidence_items[0]["key"]
    all_keys = [item["key"] for item in evidence_items]
    product_category = _product_category(payload)
    customer_claimed_condition = _bounded_text(
        payload, "customer_claimed_condition", MAX_CONDITION_CHARS
    )
    customer_text = _bounded_text(payload, "customer_text", config.max_customer_text_chars())
    order_value_usd = _order_value(http.require_field(payload, "order_value_usd"))

    size_bytes = 0
    for item in evidence_items:
        size_bytes += s3_utils.assert_object_exists(item["key"])

    dynamodb_client.create_claim(
        claim_id,
        {
            "s3_key": s3_key,
            "s3_keys": all_keys,
            "s3_url": evidence.canonical_uri(evidence_items[0]),
            "evidence": evidence_items[0],
            "evidence_bytes": size_bytes,
            "product_category": product_category,
            "customer_claimed_condition": customer_claimed_condition,
            "customer_text": customer_text,
            "order_value_usd": order_value_usd,
        },
    )

    execution_arn = _start_execution(
        claim_id,
        evidence.workflow_payload(
            claim_id=claim_id,
            evidence_items=evidence_items,
            product_category=product_category,
            customer_claimed_condition=customer_claimed_condition,
            customer_text=customer_text,
            order_value_usd=order_value_usd,
        ),
    )

    logger.info("Accepted claim %s (execution %s)", claim_id, execution_arn or "existing")
    return http.response(
        202,
        {
            "claim_id": claim_id,
            "status": dynamodb_client.STATUS_PROCESSING,
            "poll_url": f"/results/{claim_id}",
        },
    )
