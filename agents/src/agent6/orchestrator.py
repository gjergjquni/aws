"""
Agent 6 — Orchestrator

Pipeline (order is intentional):
  1. Deterministic score (60% Visual + 40% Claim)  ← BEFORE LLM
  2. Map score → approve | review | escalate (legacy advisory)
  3. Compute FRAUD / NOT_FRAUD / HUMAN_REVIEW using the 80% confidence rule
  4. Generate explanation (Nova Pro or fallback)
  5. Return result for the backend to store / display

Agent 6 does not write to DynamoDB. The backend orchestrator persists
HUMAN_REVIEW rows and returns automatic decisions to the caller.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Union

from . import models
from .explain import explain
from .scoring import compute_final_score, decide, recommend


def run(
    payload: Union[Dict[str, Any], Any],
    *,
    use_bedrock: Optional[bool] = None,
) -> Dict[str, Any]:
    """Main entry point. Same shape as Agjenti6 ``agent6.run()``."""
    data = models.validate_input(payload)
    live = (
        use_bedrock
        if use_bedrock is not None
        else os.getenv("AEGIS_BEDROCK_LIVE", "").lower() in {"1", "true", "yes"}
        or bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    )

    audit: list = [
        {
            "event": "orchestrator_received",
            "timestamp": models.utc_now_iso(),
            "claim_id": data["claim_id"],
        }
    ]

    final_score, breakdown = compute_final_score(
        data["visual_evidence_score"],
        data["claim_intelligence_score"],
    )
    action = recommend(final_score)
    metadata = data.get("metadata") or {}
    judged = decide(
        final_score=final_score,
        visual_score=data["visual_evidence_score"],
        claim_score=data["claim_intelligence_score"],
        visual_status=str(metadata.get("visual_status") or "ok"),
        claim_status=str(metadata.get("claim_status") or "ok"),
        visual_recommendation=metadata.get("visual_recommendation"),
        claim_recommendation=metadata.get("claim_recommendation"),
        visual_confidence=data.get("visual_confidence"),
        claim_confidence=data.get("claim_confidence"),
    )
    audit.append(
        {
            "event": "score_computed",
            "timestamp": models.utc_now_iso(),
            "final_score": final_score,
            "recommendation": action,
            "decision": judged["decision"],
            "confidence": judged["confidence"],
            "formula": breakdown["formula"],
            "scored_before_llm": True,
        }
    )

    explanation, model_id = explain(
        claim_id=data["claim_id"],
        final_score=final_score,
        recommendation=action,
        formula=breakdown["formula"],
        visual_score=data["visual_evidence_score"],
        claim_score=data["claim_intelligence_score"],
        description=data["description"],
        indicators=data["indicators"],
        summaries={
            "visual_evidence": data["visual_evidence_summary"],
            "claim_intelligence": data["claim_intelligence_summary"],
        },
        decision=judged["decision"],
        confidence=judged["confidence"],
        reason=judged["reason"],
        requires_human_review=judged["requires_human_review"],
        use_bedrock=live,
    )
    audit.append(
        {
            "event": "explanation_generated",
            "timestamp": models.utc_now_iso(),
            "model_id": model_id or "fallback",
        }
    )

    strongest = sorted(
        data["indicators"],
        key=lambda item: float(item.get("severity") or 0),
        reverse=True,
    )[:5]

    summary = (
        f"Claim {data['claim_id']}: decision={judged['decision']}, "
        f"confidence={judged['confidence']}, final_score={final_score}, "
        f"recommendation={action}. "
        f"{breakdown['formula']}. "
        f"Visual: {data['visual_evidence_summary'] or 'n/a'} "
        f"Claim intel: {data['claim_intelligence_summary'] or 'n/a'}"
    )

    return models.orchestrator_result(
        claim_id=data["claim_id"],
        customer_id=data.get("customer_id"),
        individual_scores={
            "visual_evidence": data["visual_evidence_score"],
            "claim_intelligence": data["claim_intelligence_score"],
        },
        final_score=final_score,
        recommendation=action,
        breakdown=breakdown,
        strongest_indicators=strongest,
        investigation_summary=summary,
        explanation=explanation,
        model_id=model_id,
        audit=audit,
        decision=judged["decision"],
        confidence=judged["confidence"],
        fraud_probability=judged["fraud_probability"],
        reason=judged["reason"],
        requires_human_review=judged["requires_human_review"],
        decision_detail=judged,
    )
