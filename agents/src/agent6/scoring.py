"""
Deterministic scoring for Agent 6 — runs BEFORE any LLM call.

    final_score = VISUAL_WEIGHT * visual_evidence + CLAIM_WEIGHT * claim_intelligence

Defaults are 0.60 / 0.40. The two weights must sum to 1.0.
Nova Pro must never recalculate or override this number.
Ported from Agjenti6/agent6/scoring.py.

Decision confidence is NOT a calibrated P(fraud). It is an explainable
combination of (1) how far the 60/40 score sits in the existing approve /
escalate bands and (2) how much Agent 1 and Agent 3 agree. Auto-decide only
when that confidence is >= 80%.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from shared import config

from . import models

VISUAL_WEIGHT = 0.60
CLAIM_WEIGHT = 0.40
APPROVE_MAX = 30.0
REVIEW_MAX = 70.0

# Recommendations that clearly lean not-fraud vs fraud. Mixed (review) is ignored.
_CLEAR_RECS = {
    "approve",
    "clear",
    "no_additional_action",
}
_FRAUD_RECS = {
    "escalate",
    "manual_investigation",
}


def compute_final_score(
    visual_evidence_score: float,
    claim_intelligence_score: float,
) -> Tuple[float, Dict[str, Any]]:
    visual_weight, claim_weight = config.agent6_weights()
    visual_contrib = round(visual_evidence_score * visual_weight, 4)
    claim_contrib = round(claim_intelligence_score * claim_weight, 4)
    final = round(min(100.0, max(0.0, visual_contrib + claim_contrib)), 2)

    formula = (
        f"({visual_evidence_score:.2f} * {visual_weight:.2f}) + "
        f"({claim_intelligence_score:.2f} * {claim_weight:.2f}) = {final:.2f}"
    )
    breakdown = models.score_breakdown(
        visual_evidence_score=visual_evidence_score,
        claim_intelligence_score=claim_intelligence_score,
        visual_weight=visual_weight,
        claim_weight=claim_weight,
        visual_contribution=round(visual_contrib, 2),
        claim_contribution=round(claim_contrib, 2),
        formula=formula,
    )
    return final, breakdown


def recommend(final_score: float) -> str:
    """approve <= 30 | review <= 70 | escalate > 70. Decision support only."""
    if final_score <= APPROVE_MAX:
        return models.APPROVE
    if final_score <= REVIEW_MAX:
        return models.REVIEW
    return models.ESCALATE


def agreement(visual_score: float, claim_score: float) -> float:
    """1.0 when both specialists match, 0.0 when they are 100 points apart."""
    return max(0.0, 1.0 - abs(visual_score - claim_score) / 100.0)


def _norm_rec(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def recommendations_conflict(visual_rec: Any, claim_rec: Any) -> bool:
    """True when one specialist is clearly 'not fraud' and the other is clearly fraud."""
    visual = _norm_rec(visual_rec)
    claim = _norm_rec(claim_rec)
    if not visual or not claim:
        return False
    return (visual in _CLEAR_RECS and claim in _FRAUD_RECS) or (
        visual in _FRAUD_RECS and claim in _CLEAR_RECS
    )


def _band(final_score: float) -> Tuple[str, float]:
    """Map the existing 30/70 bands to a lean and a 0-1 strength inside that band.

    Middle scores (30-70) have strength 0 and lean HUMAN_REVIEW, so they never
    auto-decide even when the two agents agree.
    """
    if final_score <= APPROVE_MAX:
        strength = (APPROVE_MAX - final_score) / APPROVE_MAX if APPROVE_MAX else 1.0
        return models.NOT_FRAUD, max(0.0, min(1.0, strength))
    if final_score >= REVIEW_MAX:
        span = 100.0 - REVIEW_MAX
        strength = (final_score - REVIEW_MAX) / span if span else 1.0
        return models.FRAUD, max(0.0, min(1.0, strength))
    return models.HUMAN_REVIEW, 0.0


def _quality(visual_confidence: Optional[float], claim_confidence: Optional[float]) -> float:
    """Mean of specialist analysis-confidence scores, each on 0-1. Missing → 0.7."""
    values = []
    for raw in (visual_confidence, claim_confidence):
        if raw is None:
            values.append(0.7)
            continue
        try:
            values.append(max(0.0, min(1.0, float(raw) / 100.0 if float(raw) > 1.0 else float(raw))))
        except (TypeError, ValueError):
            values.append(0.7)
    return sum(values) / len(values) if values else 0.7


def _reason(
    *,
    decision: str,
    lean: str,
    visual_score: float,
    claim_score: float,
    visual_ok: bool,
    claim_ok: bool,
    conflict: bool,
    confidence: float,
    factors: Sequence[str],
) -> str:
    if decision == models.FRAUD:
        return (
            "Both supporting agents identified strong indicators of fraudulent behavior."
        )
    if decision == models.NOT_FRAUD:
        return (
            "Both supporting agents found insufficient evidence of fraudulent behavior."
        )

    parts: list[str] = []
    if not visual_ok and not claim_ok:
        parts.append("Neither Agent 1 (visual evidence) nor Agent 3 (claim intelligence) completed successfully.")
    elif not visual_ok:
        parts.append("Agent 1 (visual evidence) did not complete successfully.")
    elif not claim_ok:
        parts.append("Agent 3 (claim intelligence) did not complete successfully.")

    visual_high = visual_score >= REVIEW_MAX
    claim_high = claim_score >= REVIEW_MAX
    visual_low = visual_score <= APPROVE_MAX
    claim_low = claim_score <= APPROVE_MAX
    if visual_ok and claim_ok and (conflict or (visual_high and claim_low) or (visual_low and claim_high)):
        if visual_score > claim_score:
            parts.append(
                "Agent 1 (visual evidence) detected suspicious transaction behavior, "
                "while Agent 3 (claim intelligence) found insufficient evidence to "
                "classify the transaction as fraudulent."
            )
        else:
            parts.append(
                "Agent 3 (claim intelligence) detected suspicious claim language, "
                "while Agent 1 (visual evidence) found insufficient evidence to "
                "classify the transaction as fraudulent."
            )
    elif lean == models.HUMAN_REVIEW:
        parts.append(
            "The combined evidence is in an intermediate range and is not decisive "
            "for either fraud or not-fraud."
        )
    else:
        parts.append(
            f"The two specialists lean {lean} but decision confidence "
            f"({confidence:.1%}) is below the {config.confidence_threshold():.0%} auto-decide threshold."
        )

    if factors and not parts:
        parts.append("; ".join(factors) + ".")
    return " ".join(parts) if parts else "The case is ambiguous and requires human review."


def decide(
    *,
    final_score: float,
    visual_score: float,
    claim_score: float,
    visual_status: str = "ok",
    claim_status: str = "ok",
    visual_recommendation: Any = None,
    claim_recommendation: Any = None,
    visual_confidence: Optional[float] = None,
    claim_confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute FRAUD / NOT_FRAUD / HUMAN_REVIEW from specialist scores.

    ``fraud_probability`` is the existing 60/40 score on 0-1.
    ``confidence`` is decision certainty. Auto-decide iff confidence >= threshold
    and both specialists succeeded.
    """
    threshold = config.confidence_threshold()
    visual_ok = str(visual_status or "").lower() == "ok"
    claim_ok = str(claim_status or "").lower() == "ok"
    both_ok = visual_ok and claim_ok
    conflict = recommendations_conflict(visual_recommendation, claim_recommendation)
    agree = agreement(visual_score, claim_score)
    lean, band_strength = _band(final_score)
    quality = _quality(visual_confidence, claim_confidence)
    fraud_probability = round(max(0.0, min(1.0, final_score / 100.0)), 4)

    # 0.80 floor + up to 0.20 from (band strength, agreement). The middle band
    # has strength 0, so confidence stays <= 0.90 even with full agreement.
    raw = 0.80 + 0.20 * (0.5 * band_strength + 0.5 * agree)
    factors: list[str] = []

    if not both_ok:
        raw = min(raw, 0.80)
        factors.append("incomplete specialist output")
    if conflict:
        raw = min(raw, 0.90)
        factors.append("specialist recommendations conflict")
    visual_n = _norm_rec(visual_recommendation)
    claim_n = _norm_rec(claim_recommendation)
    if lean == models.FRAUD and visual_n in _CLEAR_RECS and claim_n in _CLEAR_RECS:
        raw = min(raw, 0.90)
        factors.append("risk scores are high but both specialists recommended no additional action")
    if lean == models.NOT_FRAUD and visual_n in _FRAUD_RECS and claim_n in _FRAUD_RECS:
        raw = min(raw, 0.90)
        factors.append("risk scores are low but both specialists recommended escalation")
    if abs(visual_score - claim_score) > 40:
        raw = min(raw, 0.90)
        factors.append("specialist scores disagree by more than 40 points")
    if quality < 0.5:
        raw = min(raw, 0.90)
        factors.append("analysis-quality scores are low")

    confidence = round(min(1.0, max(0.0, raw)), 4)

    if both_ok and lean != models.HUMAN_REVIEW and confidence >= threshold:
        decision = lean
        requires_review = False
    else:
        decision = models.HUMAN_REVIEW
        requires_review = True
        if lean == models.HUMAN_REVIEW:
            factors.append("combined score is in the ambiguous 30-70 band")
        elif confidence < threshold:
            factors.append(f"decision confidence {confidence:.2f} is below {threshold:.2f}")

    reason = _reason(
        decision=decision,
        lean=lean,
        visual_score=visual_score,
        claim_score=claim_score,
        visual_ok=visual_ok,
        claim_ok=claim_ok,
        conflict=conflict,
        confidence=confidence,
        factors=factors,
    )
    return {
        "decision": decision,
        "confidence": confidence,
        "fraud_probability": fraud_probability,
        "requires_human_review": requires_review,
        "reason": reason,
        "lean": lean,
        "agreement": round(agree, 4),
        "band_strength": round(band_strength, 4),
        "analysis_quality": round(quality, 4),
        "ambiguity_factors": factors,
        "threshold": threshold,
    }
