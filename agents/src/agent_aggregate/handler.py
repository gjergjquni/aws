"""Aggregator — Agent 6 is the final decision-maker.

Runs after the parallel Agent 1 (visual) and Agent 3 (claim intelligence)
branches. Each branch catches its own failure, so this function always
receives input.

Agent 6 computes the 60/40 score and the 80% confidence decision. This
handler is the backend orchestrator: it persists the verdict and, when the
decision is HUMAN_REVIEW, writes a DynamoDB review row. DynamoDB is not
called from inside Agent 6.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent6.models import HUMAN_REVIEW
from shared import config, dynamodb_client
from shared.errors import SchemaError, ValidationError
from shared.finalize import persist_decision, run_agent6

logger = config.get_logger(__name__)

_SCORE_FIELDS = {
    "visual": ("risk_score", "visual_risk_score"),
    "claim": ("risk_score", "language_risk_score"),
}

_RECOMMENDATION_MAP = {
    "clear": "clear",
    "review": "review",
    "escalate": "escalate",
    "no_additional_action": "clear",
    "review_evidence": "review",
    "review_claim": "review",
    "manual_investigation": "escalate",
}


def _by_agent(results: Any) -> Dict[str, Dict[str, Any]]:
    """Index the parallel branch outputs by agent name."""
    indexed: Dict[str, Dict[str, Any]] = {}
    if not isinstance(results, list):
        return indexed
    for entry in results:
        if isinstance(entry, dict) and isinstance(entry.get("agent"), str):
            indexed[entry["agent"]] = entry
    return indexed


def _score_of(entry: Optional[Dict[str, Any]], fields: Any) -> Optional[int]:
    if not entry or entry.get("status") != "ok":
        return None
    result = entry.get("result")
    if not isinstance(result, dict):
        return None
    names = fields if isinstance(fields, (list, tuple)) else (fields,)
    for field in names:
        value = result.get(field)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value == int(value):
            return int(value)
    return None


def _recommendation_of(entry: Optional[Dict[str, Any]]) -> Optional[str]:
    if not entry or entry.get("status") != "ok":
        return None
    result = entry.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("recommendation"), str):
        return None
    raw = result["recommendation"].strip().lower()
    return _RECOMMENDATION_MAP.get(raw)


def _decide(combined: int, recommendations: List[str]) -> str:
    if "escalate" in recommendations or combined >= config.escalate_threshold():
        return "escalate"
    if "review" in recommendations or combined >= config.review_threshold():
        return "review"
    return "clear"


def _s3_url(event: Dict[str, Any]) -> str:
    evidence_block = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
    bucket = str(evidence_block.get("bucket") or "")
    key = str(evidence_block.get("key") or event.get("s3_key") or "")
    if not bucket:
        try:
            bucket = config.bucket_name()
        except Exception:  # noqa: BLE001 — local runs may omit the bucket
            bucket = ""
    if bucket and key:
        return f"s3://{bucket}/{key}"
    return str(event.get("s3_image_url") or event.get("s3_url") or key or "")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    claim_id = event["claim_id"]
    indexed = _by_agent(event.get("results"))
    visual = indexed.get("visual")
    claim = indexed.get("claim")
    visual_ok = bool(visual) and visual.get("status") == "ok" and isinstance(visual.get("result"), dict)
    claim_ok = bool(claim) and claim.get("status") == "ok" and isinstance(claim.get("result"), dict)
    both_failed = not visual_ok and not claim_ok

    if both_failed:
        message = "Both agents failed; no verdict could be produced"
        logger.error("%s for claim %s", message, claim_id)
        failed = {
            "decision": HUMAN_REVIEW,
            "confidence": 0.0,
            "fraud_probability": None,
            "reason": message,
            "requires_human_review": True,
            "final_score": None,
            "recommendation": "review",
            "status": dynamodb_client.STATUS_FAILED,
            "claim_id": claim_id,
        }
        public = persist_decision(
            claim_id,
            failed,
            visual_entry=visual,
            claim_entry=claim,
            message=str(event.get("customer_text") or event.get("message") or ""),
            s3_url=_s3_url(event),
            both_failed=True,
        )
        return {
            "claim_id": claim_id,
            "status": dynamodb_client.STATUS_FAILED,
            "verdict": public,
        }

    try:
        agent6 = run_agent6(
            visual,
            claim,
            claim_id=claim_id,
            description=str(event.get("customer_text") or event.get("message") or ""),
        )
    except (ValidationError, SchemaError) as exc:
        logger.exception("Agent 6 rejected malformed specialist output for %s", claim_id)
        failed = {
            "decision": HUMAN_REVIEW,
            "confidence": 0.0,
            "reason": f"Agent 6 could not read specialist output: {exc}",
            "requires_human_review": True,
            "final_score": None,
            "recommendation": "review",
            "claim_id": claim_id,
        }
        public = persist_decision(
            claim_id,
            failed,
            visual_entry=visual,
            claim_entry=claim,
            message=str(event.get("customer_text") or ""),
            s3_url=_s3_url(event),
            both_failed=True,
        )
        public["status"] = "failed"
        return {"claim_id": claim_id, "status": dynamodb_client.STATUS_FAILED, "verdict": public}

    public = persist_decision(
        claim_id,
        agent6,
        visual_entry=visual,
        claim_entry=claim,
        message=str(event.get("customer_text") or event.get("message") or ""),
        s3_url=_s3_url(event),
        both_failed=False,
    )
    logger.info(
        "Claim %s Agent 6 decision=%s confidence=%s review=%s",
        claim_id,
        agent6.get("decision"),
        agent6.get("confidence"),
        agent6.get("requires_human_review"),
    )
    return {
        "claim_id": claim_id,
        "status": public.get("status"),
        "verdict": public,
        "agent6": {
            "decision": agent6.get("decision"),
            "confidence": agent6.get("confidence"),
            "reason": agent6.get("reason"),
        },
    }
