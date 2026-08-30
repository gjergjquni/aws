"""Deterministic scoring for the visual and claim agents.

The LLM emits findings. Application code computes the 0-100 risk number.
Confidence is confidence in the analysis (tool availability), not P(fraud).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import config

# ---------------------------------------------------------------------------
# Agent 1 — visual evidence
# ---------------------------------------------------------------------------

# category -> (max contribution, default if severity missing)
_VISUAL_CATEGORY_WEIGHTS: Dict[str, Tuple[int, int, int]] = {
    # (LOW, MEDIUM, HIGH) bounded contributions
    "MANIPULATION": (15, 25, 35),
    "DUPLICATE": (10, 18, 25),
    "CROSS_IMAGE": (10, 18, 25),
    "OBJECT_MISMATCH": (8, 15, 20),
    "DAMAGE_INCONSISTENCY": (8, 15, 20),
    "SCENE_MISMATCH": (6, 12, 18),
    "LIGHTING": (4, 8, 12),
    "AI_SYNTHETIC": (10, 18, 25),
    "METADATA": (3, 8, 12),
    "COMPRESSION": (2, 5, 8),
    "QUALITY": (2, 5, 8),
    "REKOGNITION_LABEL": (4, 8, 12),
    "REKOGNITION_TEXT": (3, 6, 10),
    "OTHER": (3, 6, 10),
}

# Missing EXIF / social recompression are weak by policy even if flagged HIGH.
_WEAK_METADATA_FLAGS = {
    "missing_exif",
    "no_camera_make",
    "no_original_timestamp",
}

_SEVERITY_INDEX = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _severity_points(category: str, severity: str, weights: Mapping[str, Tuple[int, int, int]]) -> int:
    low, medium, high = weights.get(category, weights.get("OTHER", (3, 6, 10)))
    return (low, medium, high)[_SEVERITY_INDEX.get(severity, 0)]


def _max_by_category(
    findings: Sequence[Mapping[str, str]],
    weights: Mapping[str, Tuple[int, int, int]],
) -> Dict[str, int]:
    best: Dict[str, int] = {}
    for finding in findings:
        category = finding.get("category", "OTHER")
        severity = finding.get("severity", "LOW")
        points = _severity_points(category, severity, weights)
        if points > best.get(category, 0):
            best[category] = points
    return best


def visual_risk_score(
    findings: Sequence[Mapping[str, str]],
    *,
    metadata_problems: Optional[Sequence[str]] = None,
    hive_ai_score: Optional[float] = None,
    duplicate_pairs: int = 0,
) -> int:
    """Bounded additive score. Independent categories stack; duplicates do not."""
    contributions = _max_by_category(findings, _VISUAL_CATEGORY_WEIGHTS)

    problems = list(metadata_problems or [])
    if problems and "METADATA" not in contributions:
        if set(problems) <= _WEAK_METADATA_FLAGS:
            contributions["METADATA"] = 5
        elif "ai_tool_in_metadata" in problems or "future_timestamp" in problems:
            contributions["METADATA"] = 12
        elif any(flag.startswith("edited_") for flag in problems):
            contributions["METADATA"] = 8
        else:
            contributions["METADATA"] = 5

    if hive_ai_score is not None:
        # Classifier output, not proof. High scores add a bounded AI_SYNTHETIC term
        # only when that category is not already represented more strongly.
        hive_points = 0
        if hive_ai_score >= 0.9:
            hive_points = 25
        elif hive_ai_score >= 0.7:
            hive_points = 15
        elif hive_ai_score >= 0.5:
            hive_points = 8
        if hive_points:
            contributions["AI_SYNTHETIC"] = max(contributions.get("AI_SYNTHETIC", 0), hive_points)

    if duplicate_pairs and "DUPLICATE" not in contributions:
        contributions["DUPLICATE"] = 18 if duplicate_pairs == 1 else 25

    total = sum(contributions.values())
    return max(0, min(100, total))


def visual_confidence_score(
    *,
    rekognition_available: bool,
    hive_available: bool,
    image_count: int,
    metadata_present: bool,
    bedrock_succeeded: bool,
    corrupt_or_partial: bool = False,
) -> int:
    score = 55
    if bedrock_succeeded:
        score += 15
    if rekognition_available:
        score += 15
    if hive_available:
        score += 5
    if metadata_present:
        score += 5
    if image_count >= 2:
        score += 5
    if not rekognition_available:
        score -= 10
    if not bedrock_succeeded:
        score -= 25
    if corrupt_or_partial:
        score -= 20
    return max(0, min(100, score))


def visual_recommendation(risk_score: int, findings: Sequence[Mapping[str, str]]) -> str:
    strong_categories = {
        finding.get("category")
        for finding in findings
        if finding.get("severity") == "HIGH"
        and finding.get("category")
        in {"MANIPULATION", "DUPLICATE", "OBJECT_MISMATCH", "DAMAGE_INCONSISTENCY", "AI_SYNTHETIC"}
    }
    if risk_score >= config.escalate_threshold() or len(strong_categories) >= 2:
        return "MANUAL_INVESTIGATION"
    if risk_score >= config.review_threshold() or strong_categories:
        return "REVIEW_EVIDENCE"
    return "NO_ADDITIONAL_ACTION"


# ---------------------------------------------------------------------------
# Agent 2 — claim intelligence
# ---------------------------------------------------------------------------

_CLAIM_CATEGORY_WEIGHTS: Dict[str, Tuple[int, int, int]] = {
    "CONTRADICTION": (12, 22, 30),
    "TEMPLATE_SIMILARITY": (8, 16, 24),
    "CONTEXT": (8, 14, 20),
    "URGENCY": (4, 8, 10),  # urgency alone cannot produce HIGH
    "COMPLETENESS": (4, 8, 10),
    "OTHER": (4, 8, 12),
}


def claim_risk_score(
    findings: Sequence[Mapping[str, str]],
    *,
    retrieved_patterns: Optional[Sequence[Mapping[str, Any]]] = None,
) -> int:
    contributions = _max_by_category(findings, _CLAIM_CATEGORY_WEIGHTS)

    top_similarity = 0.0
    for pattern in retrieved_patterns or []:
        try:
            top_similarity = max(top_similarity, float(pattern.get("similarity_score") or 0.0))
        except (TypeError, ValueError):
            continue
    if top_similarity >= 0.88:
        contributions["TEMPLATE_SIMILARITY"] = max(contributions.get("TEMPLATE_SIMILARITY", 0), 24)
    elif top_similarity >= 0.80:
        contributions["TEMPLATE_SIMILARITY"] = max(contributions.get("TEMPLATE_SIMILARITY", 0), 16)
    elif top_similarity >= 0.72:
        contributions["TEMPLATE_SIMILARITY"] = max(contributions.get("TEMPLATE_SIMILARITY", 0), 8)

    total = sum(contributions.values())
    # A single URGENCY finding cannot push the claim into HIGH.
    independent = {key for key in contributions if key != "URGENCY" and contributions[key] > 0}
    if not independent:
        total = min(total, config.review_threshold() - 1)
    return max(0, min(100, total))


def claim_confidence_score(
    *,
    retrieval_mode: str,
    bedrock_succeeded: bool,
    retrieved_count: int,
    claim_text_chars: int,
) -> int:
    score = 50
    if bedrock_succeeded:
        score += 20
    if retrieval_mode == "OPENSEARCH":
        score += 15
    elif retrieval_mode == "IN_MEMORY":
        score += 10
    elif retrieval_mode == "LEXICAL":
        score += 0
        score -= 10
    else:
        score -= 15
    if retrieved_count:
        score += min(10, retrieved_count * 3)
    if claim_text_chars < 40:
        score -= 10
    elif claim_text_chars >= 120:
        score += 5
    if not bedrock_succeeded:
        score -= 20
    return max(0, min(100, score))


def claim_recommendation(risk_score: int, findings: Sequence[Mapping[str, str]]) -> str:
    contradictions = [
        finding
        for finding in findings
        if finding.get("category") == "CONTRADICTION" and finding.get("severity") in {"MEDIUM", "HIGH"}
    ]
    if risk_score >= config.escalate_threshold() or len(contradictions) >= 2:
        return "MANUAL_INVESTIGATION"
    if risk_score >= config.review_threshold() or contradictions:
        return "REVIEW_CLAIM"
    return "NO_ADDITIONAL_ACTION"


def categories_present(findings: Iterable[Mapping[str, str]]) -> List[str]:
    seen = []
    for finding in findings:
        category = finding.get("category")
        if category and category not in seen:
            seen.append(category)
    return seen
