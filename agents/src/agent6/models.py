"""Agent 6 I/O — same contract as Agjenti6/agent6/models.py, without pydantic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.errors import ValidationError

APPROVE = "approve"
REVIEW = "review"
ESCALATE = "escalate"
RECOMMENDATIONS = (APPROVE, REVIEW, ESCALATE)

FRAUD = "FRAUD"
NOT_FRAUD = "NOT_FRAUD"
HUMAN_REVIEW = "HUMAN_REVIEW"
DECISIONS = (FRAUD, NOT_FRAUD, HUMAN_REVIEW)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a number") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValidationError(f"{field} must be a finite number")
    if number < 0 or number > 100:
        raise ValidationError(f"{field} must be between 0 and 100")
    return number


def validate_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("Agent 6 payload must be an object")
    claim_id = str(payload.get("claim_id") or "").strip()
    if not claim_id:
        raise ValidationError("Missing required field: claim_id")
    indicators = payload.get("indicators") or []
    if not isinstance(indicators, list):
        raise ValidationError("indicators must be a list")
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "claim_id": claim_id,
        "customer_id": payload.get("customer_id"),
        "visual_evidence_score": _score(
            payload.get("visual_evidence_score"), "visual_evidence_score"
        ),
        "claim_intelligence_score": _score(
            payload.get("claim_intelligence_score"), "claim_intelligence_score"
        ),
        "visual_evidence_summary": str(payload.get("visual_evidence_summary") or ""),
        "claim_intelligence_summary": str(payload.get("claim_intelligence_summary") or ""),
        "visual_confidence": payload.get("visual_confidence"),
        "claim_confidence": payload.get("claim_confidence"),
        "description": str(payload.get("description") or ""),
        "indicators": [item for item in indicators if isinstance(item, dict)],
        "metadata": metadata,
    }


def score_breakdown(
    *,
    visual_evidence_score: float,
    claim_intelligence_score: float,
    visual_weight: float,
    claim_weight: float,
    visual_contribution: float,
    claim_contribution: float,
    formula: str,
) -> Dict[str, Any]:
    return {
        "visual_evidence_score": visual_evidence_score,
        "visual_weight": visual_weight,
        "visual_contribution": visual_contribution,
        "claim_intelligence_score": claim_intelligence_score,
        "claim_weight": claim_weight,
        "claim_contribution": claim_contribution,
        "formula": formula,
        "scored_before_llm": True,
    }


def orchestrator_result(
    *,
    claim_id: str,
    customer_id: Optional[str],
    individual_scores: Dict[str, float],
    final_score: float,
    recommendation: str,
    breakdown: Dict[str, Any],
    strongest_indicators: List[Dict[str, Any]],
    investigation_summary: str,
    explanation: str,
    model_id: Optional[str],
    audit: List[Dict[str, Any]],
    decision: str = HUMAN_REVIEW,
    confidence: float = 0.0,
    fraud_probability: float = 0.0,
    reason: str = "",
    requires_human_review: bool = True,
    decision_detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if recommendation not in RECOMMENDATIONS:
        raise ValidationError(f"recommendation must be one of {RECOMMENDATIONS}")
    if decision not in DECISIONS:
        raise ValidationError(f"decision must be one of {DECISIONS}")
    needs_human = bool(requires_human_review) or decision == HUMAN_REVIEW
    return {
        "claim_id": claim_id,
        "customer_id": customer_id,
        "individual_scores": individual_scores,
        "final_score": final_score,
        "recommendation": recommendation,
        "decision": decision,
        "confidence": confidence,
        "fraud_probability": fraud_probability,
        "reason": reason or explanation,
        "score_breakdown": breakdown,
        "strongest_indicators": strongest_indicators,
        "investigation_summary": investigation_summary,
        "explanation": explanation,
        "model_id": model_id,
        "human_oversight_required": needs_human,
        "requires_human_review": needs_human,
        "auto_refund_allowed": False,
        "status": "pending_human_review" if needs_human else "completed",
        "decision_detail": decision_detail or {},
        "audit": audit,
        "created_at": utc_now_iso(),
        "agent": "agent-6-orchestrator",
        "agent_version": "1.1.0",
        "investigation_id": str(uuid4()),
    }


def public_decision(result: Dict[str, Any], *, case_id: Optional[str] = None) -> Dict[str, Any]:
    """Frontend-facing Agent 6 payload. Hides specialist internals."""
    resolved = str(case_id or result.get("claim_id") or "")
    needs_human = bool(result.get("requires_human_review"))
    decision = result.get("decision") or (HUMAN_REVIEW if needs_human else None)
    body: Dict[str, Any] = {
        "case_id": resolved,
        "decision": decision,
        "confidence": result.get("confidence"),
        "fraud_probability": result.get("fraud_probability"),
        "reason": result.get("reason") or result.get("explanation") or "",
        "requires_human_review": needs_human,
    }
    if needs_human:
        body["status"] = "pending_human_review"
        body["message"] = "This case requires human review."
    else:
        body["status"] = "completed"
    return body
