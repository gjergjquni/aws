"""Strict output contracts for Agent 1 (visual) and Agent 2 (claim).

The LLM is not allowed to invent the response shape. Application code validates
model fragments, then assembles the public result. Invalid model JSON is a
controlled failure, never silently coerced into a successful analysis.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import coerce, config
from .errors import SchemaError

VISUAL_FINDING_CATEGORIES = (
    "METADATA",
    "COMPRESSION",
    "QUALITY",
    "MANIPULATION",
    "DUPLICATE",
    "OBJECT_MISMATCH",
    "DAMAGE_INCONSISTENCY",
    "LIGHTING",
    "SCENE_MISMATCH",
    "AI_SYNTHETIC",
    "REKOGNITION_LABEL",
    "REKOGNITION_TEXT",
    "CROSS_IMAGE",
    "OTHER",
)

VISUAL_FINDING_SOURCES = (
    "rekognition",
    "bedrock",
    "metadata",
    "image_analysis",
    "hive",
)

CLAIM_FINDING_CATEGORIES = (
    "CONTRADICTION",
    "TEMPLATE_SIMILARITY",
    "URGENCY",
    "COMPLETENESS",
    "CONTEXT",
    "OTHER",
)

CLAIM_FINDING_SOURCES = ("claim_text", "opensearch", "bedrock", "lexical_fallback", "in_memory_vector")

RETRIEVAL_MODES = ("OPENSEARCH", "IN_MEMORY", "LEXICAL", "UNAVAILABLE")

_VISUAL_MODEL_REQUIRED = ("findings", "explanation")
_CLAIM_MODEL_REQUIRED = ("findings", "explanation")


def risk_level_for_score(score: int) -> str:
    if score >= config.escalate_threshold():
        return "HIGH"
    if score >= config.review_threshold():
        return "MEDIUM"
    return "LOW"


def _require_dict(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{label} must be a JSON object")
    return value


def _enum(value: Any, allowed: Iterable[str], field: str, default: Optional[str] = None) -> str:
    if isinstance(value, str):
        candidate = value.strip()
        lookup = {item.upper(): item for item in allowed}
        if candidate.upper() in lookup:
            return lookup[candidate.upper()]
        if candidate in allowed:
            return candidate
    if default is not None:
        return default
    raise SchemaError(f"{field} must be one of {sorted(set(allowed))}")


def _finding(
    raw: Any,
    *,
    categories: Sequence[str],
    sources: Sequence[str],
    default_source: str,
) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        return None
    description = coerce.as_text(raw.get("description"), max_length=500)
    evidence = coerce.as_text(raw.get("evidence"), max_length=800)
    if not description:
        return None
    try:
        category = _enum(raw.get("category"), categories, "category")
        severity = _enum(raw.get("severity"), config.SEVERITIES, "severity", default="LOW")
        source = _enum(raw.get("source"), sources, "source", default=default_source)
    except SchemaError:
        return None
    return {
        "category": category,
        "severity": severity,
        "description": description,
        "evidence": evidence or description,
        "source": source,
    }


def _findings_list(
    raw: Any,
    *,
    categories: Sequence[str],
    sources: Sequence[str],
    default_source: str,
    max_items: int = 25,
) -> List[Dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SchemaError("findings must be a list")
    items: List[Dict[str, str]] = []
    for entry in raw:
        finding = _finding(
            entry, categories=categories, sources=sources, default_source=default_source
        )
        if finding:
            items.append(finding)
        if len(items) >= max_items:
            break
    return items


def _text_list(raw: Any, max_items: int = 20, max_length: int = 400) -> List[str]:
    return coerce.as_text_list(raw, max_items=max_items, max_length=max_length)


def parse_visual_model_output(raw: Any) -> Dict[str, Any]:
    """Validate the Bedrock fragment for Agent 1. Does not include scores."""
    payload = _require_dict(raw, "visual model output")
    missing = [field for field in _VISUAL_MODEL_REQUIRED if field not in payload]
    if missing:
        raise SchemaError(f"visual model output missing fields: {', '.join(missing)}")
    explanation = coerce.as_text(payload.get("explanation"), max_length=1000)
    if not explanation:
        raise SchemaError("visual model output explanation is empty")
    return {
        "findings": _findings_list(
            payload.get("findings"),
            categories=VISUAL_FINDING_CATEGORIES,
            sources=VISUAL_FINDING_SOURCES,
            default_source="bedrock",
        ),
        "cross_image_findings": _findings_list(
            payload.get("cross_image_findings"),
            categories=VISUAL_FINDING_CATEGORIES,
            sources=VISUAL_FINDING_SOURCES,
            default_source="bedrock",
        ),
        "limitations": _text_list(payload.get("limitations")),
        "explanation": explanation,
    }


def parse_claim_model_output(raw: Any) -> Dict[str, Any]:
    """Validate the Bedrock fragment for Agent 2. Does not include scores."""
    payload = _require_dict(raw, "claim model output")
    missing = [field for field in _CLAIM_MODEL_REQUIRED if field not in payload]
    if missing:
        raise SchemaError(f"claim model output missing fields: {', '.join(missing)}")
    explanation = coerce.as_text(payload.get("explanation"), max_length=1000)
    if not explanation:
        raise SchemaError("claim model output explanation is empty")
    return {
        "findings": _findings_list(
            payload.get("findings"),
            categories=CLAIM_FINDING_CATEGORIES,
            sources=CLAIM_FINDING_SOURCES,
            default_source="bedrock",
        ),
        "limitations": _text_list(payload.get("limitations")),
        "explanation": explanation,
    }


def visual_result(
    *,
    claim_id: str,
    risk_score: int,
    confidence_score: int,
    findings: Sequence[Mapping[str, str]],
    cross_image_findings: Sequence[Mapping[str, str]],
    limitations: Sequence[str],
    explanation: str,
    recommendation: str,
    extras: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    score = coerce.as_int(risk_score, default=0)
    confidence = coerce.as_int(confidence_score, default=0)
    rec = _enum(recommendation, config.VISUAL_RECOMMENDATIONS, "recommendation")
    body: Dict[str, Any] = {
        "agent": "visual_evidence",
        "claim_id": claim_id,
        "risk_score": score,
        "confidence_score": confidence,
        "risk_level": risk_level_for_score(score),
        "findings": list(findings),
        "cross_image_findings": list(cross_image_findings),
        "limitations": list(limitations),
        "explanation": coerce.as_text(explanation, default="No explanation provided.", max_length=1000),
        "recommendation": rec,
        # Aggregator compatibility — do not remove.
        "visual_risk_score": score,
    }
    if extras:
        body.update(extras)
    return body


def claim_result(
    *,
    claim_id: str,
    risk_score: int,
    confidence_score: int,
    findings: Sequence[Mapping[str, str]],
    retrieved_patterns: Sequence[Mapping[str, Any]],
    limitations: Sequence[str],
    explanation: str,
    recommendation: str,
    extras: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    score = coerce.as_int(risk_score, default=0)
    confidence = coerce.as_int(confidence_score, default=0)
    rec = _enum(recommendation, config.CLAIM_RECOMMENDATIONS, "recommendation")
    body: Dict[str, Any] = {
        "agent": "claim_intelligence",
        "claim_id": claim_id,
        "risk_score": score,
        "confidence_score": confidence,
        "risk_level": risk_level_for_score(score),
        "findings": list(findings),
        "retrieved_patterns": list(retrieved_patterns),
        "limitations": list(limitations),
        "explanation": coerce.as_text(explanation, default="No explanation provided.", max_length=1000),
        "recommendation": rec,
        # Aggregator compatibility — do not remove.
        "language_risk_score": score,
    }
    if extras:
        body.update(extras)
    return body


def retrieved_pattern(
    *,
    pattern_id: str,
    similarity_score: float,
    description: str,
    source: str,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "pattern_id": coerce.as_text(pattern_id, max_length=120),
        "similarity_score": round(max(0.0, min(1.0, float(similarity_score))), 4),
        "description": coerce.as_text(description, max_length=800),
        "source": coerce.as_text(source, max_length=60),
    }
    if extra:
        item.update(extra)
    return item


def assert_score_bounds(result: Mapping[str, Any]) -> None:
    for field in ("risk_score", "confidence_score"):
        value = result.get(field)
        if not isinstance(value, int) or value < 0 or value > 100:
            raise SchemaError(f"{field} must be an integer in 0-100, got {value!r}")


def merge_unique_findings(*groups: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
    """Keep first occurrence of (category, source, description)."""
    seen: set[Tuple[str, str, str]] = set()
    merged: List[Dict[str, str]] = []
    for group in groups:
        for finding in group:
            key = (
                finding.get("category", ""),
                finding.get("source", ""),
                finding.get("description", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(dict(finding))
    return merged
