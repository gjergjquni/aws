"""Backend orchestration around Agent 6.

Agent 6 only reasons. This module persists the verdict, writes a DynamoDB
review row when the decision is HUMAN_REVIEW, and builds the public API body.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from agent6 import public_decision, run_from_agents
from agent6.models import HUMAN_REVIEW
from shared import config, dynamodb_client

logger = config.get_logger(__name__)


def run_agent6(
    visual_output: Any,
    claim_output: Any,
    *,
    claim_id: str,
    description: str = "",
    use_bedrock: Optional[bool] = None,
) -> Dict[str, Any]:
    return run_from_agents(
        visual_output,
        claim_output,
        claim_id=claim_id,
        description=description,
        use_bedrock=use_bedrock,
    )


def persist_decision(
    claim_id: str,
    agent6_result: Dict[str, Any],
    *,
    visual_entry: Any = None,
    claim_entry: Any = None,
    message: str = "",
    s3_url: str = "",
    both_failed: bool = False,
) -> Dict[str, Any]:
    """Write VERDICT (+ REVIEW when needed) and update META status.

    Returns the frontend-facing analyze payload.
    """
    public = public_decision(agent6_result, case_id=claim_id)
    verdict = {
        "combined_risk_score": agent6_result.get("final_score"),
        "recommendation": agent6_result.get("recommendation"),
        "decision": agent6_result.get("decision"),
        "confidence": agent6_result.get("confidence"),
        "fraud_probability": agent6_result.get("fraud_probability"),
        "reason": agent6_result.get("reason"),
        "requires_human_review": agent6_result.get("requires_human_review"),
        "degraded": not (
            _ok(visual_entry) and _ok(claim_entry)
        ),
        "agents_succeeded": [
            name
            for name, entry in (("visual", visual_entry), ("claim", claim_entry))
            if _ok(entry)
        ],
        "agent_scores": {
            "visual": _score(visual_entry, ("risk_score", "visual_risk_score")),
            "claim": _score(claim_entry, ("risk_score", "language_risk_score")),
        },
        "agent6": {
            "decision": agent6_result.get("decision"),
            "confidence": agent6_result.get("confidence"),
            "reason": agent6_result.get("reason"),
            "final_score": agent6_result.get("final_score"),
            "recommendation": agent6_result.get("recommendation"),
        },
    }

    if config.persist_results():
        dynamodb_client.save_verdict(claim_id, verdict)
        if both_failed:
            dynamodb_client.set_claim_status(claim_id, dynamodb_client.STATUS_FAILED)
            public["status"] = dynamodb_client.STATUS_FAILED
            public["decision"] = None
            public["message"] = "Both specialist agents failed; no automatic decision was produced."
            return public

        if agent6_result.get("decision") == HUMAN_REVIEW or agent6_result.get(
            "requires_human_review"
        ):
            dynamodb_client.save_pending_review(
                claim_id,
                message=message,
                s3_url=s3_url,
                agent_1_result=visual_entry,
                agent_3_result=claim_entry,
                agent_6_result=agent6_result,
            )
            dynamodb_client.set_claim_status(claim_id, dynamodb_client.STATUS_PENDING_REVIEW)
            public["status"] = "pending_human_review"
            public["message"] = "This case requires human review."
        else:
            dynamodb_client.set_claim_status(claim_id, dynamodb_client.STATUS_COMPLETE)
            public["status"] = "completed"
    else:
        logger.info("Skipping DynamoDB persist for Agent 6 decision (DYNAMODB_TABLE unset)")
        if both_failed:
            public["status"] = "failed"
            public["decision"] = None
            public["message"] = "Both specialist agents failed; no automatic decision was produced."
        elif agent6_result.get("requires_human_review"):
            public["status"] = "pending_human_review"
            public["message"] = "This case requires human review."
        else:
            public["status"] = "completed"

    return public


def _ok(entry: Any) -> bool:
    return isinstance(entry, dict) and str(entry.get("status") or "").lower() == "ok"


def _score(entry: Any, fields: tuple) -> Optional[float]:
    if not _ok(entry):
        return None
    result = entry.get("result")
    if not isinstance(result, dict):
        return None
    for field in fields:
        value = result.get(field)
        if isinstance(value, (int, float)):
            return float(value)
    return None
