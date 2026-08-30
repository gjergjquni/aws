"""Amazon Nova Pro explanation — AFTER scoring only.

Uses the swarm Bedrock Converse client (inference profile), not a hardcoded
bare model ID. Ported from Agjenti6/agent6/explain.py.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from shared import bedrock_client, config

logger = config.get_logger(__name__)

SYSTEM = (
    "You are the Aegis Swarm Orchestrator explainer. "
    "A deterministic final_score, recommendation, decision, and confidence were "
    "ALREADY calculated. Do NOT invent a different score, recommendation, or decision. "
    "If requires_human_review is false, do not ask for a human reviewer. "
    "If the decision is HUMAN_REVIEW, explain why the case is ambiguous. "
    "Write a clear investigation explanation. Respond with plain text only (2-5 sentences)."
)


def explain(
    *,
    claim_id: str,
    final_score: float,
    recommendation: str,
    formula: str,
    visual_score: float,
    claim_score: float,
    description: str = "",
    indicators: Optional[List[Dict[str, Any]]] = None,
    summaries: Optional[Dict[str, str]] = None,
    decision: str = "HUMAN_REVIEW",
    confidence: float = 0.0,
    reason: str = "",
    requires_human_review: bool = True,
    use_bedrock: bool = False,
) -> Tuple[str, Optional[str]]:
    """Return (explanation, model_id). Uses fallback text unless use_bedrock=True."""
    if not use_bedrock:
        return (
            _fallback(
                claim_id,
                final_score,
                recommendation,
                formula,
                visual_score,
                claim_score,
                decision=decision,
                confidence=confidence,
                reason=reason,
                requires_human_review=requires_human_review,
            ),
            None,
        )

    oversight = (
        "Explain why a human must review this case."
        if requires_human_review
        else "Do not request human review; the automatic decision stands."
    )
    user = (
        f"Claim {claim_id} has final_score={final_score} "
        f"(formula: {formula}), recommendation={recommendation}, "
        f"decision={decision}, confidence={confidence}. "
        f"Deterministic reason: {reason or 'n/a'}. "
        f"Visual Evidence={visual_score}, Claim Intelligence={claim_score}. "
        f"Description: {description or 'n/a'}. "
        f"Indicators: {json.dumps(indicators or [])[:800]}. "
        f"Summaries: {json.dumps(summaries or {})[:800]}. "
        f"{oversight}"
    )
    try:
        text = bedrock_client.complete_text(SYSTEM, user).strip()
        if not text:
            raise ValueError("Bedrock returned empty explanation")
        return text, config.model_id()
    except Exception as exc:  # noqa: BLE001 — same policy as Agjenti6: never fail the score
        logger.warning("Nova Pro explanation failed, using fallback: %s", exc)
        return (
            _fallback(
                claim_id,
                final_score,
                recommendation,
                formula,
                visual_score,
                claim_score,
                decision=decision,
                confidence=confidence,
                reason=reason,
                requires_human_review=requires_human_review,
            ),
            None,
        )


def _fallback(
    claim_id: str,
    final_score: float,
    recommendation: str,
    formula: str,
    visual_score: float,
    claim_score: float,
    *,
    decision: str = "HUMAN_REVIEW",
    confidence: float = 0.0,
    reason: str = "",
    requires_human_review: bool = True,
) -> str:
    oversight = (
        "A human investigator must review before any refund decision."
        if requires_human_review
        else "No human review is required; this is an automatic decision."
    )
    detail = reason or f"Recommended action: {recommendation}."
    return (
        f"Claim {claim_id} scored {final_score}/100 using {formula} "
        f"(60% Visual Evidence={visual_score}, 40% Claim Intelligence={claim_score}). "
        f"Decision: {decision} (confidence {confidence:.2f}). "
        f"Advisory recommendation: {recommendation}. {detail} "
        f"Score was calculated before any LLM call. {oversight}"
    )
