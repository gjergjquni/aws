"""Connect Agent 1 (visual) and Agent 2 (claim) packets to Agent 6.

Accepts either the inner result dicts or the lambda wrappers
``{"agent", "status", "result", "error"}``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from .orchestrator import run
from shared import coerce

_SEVERITY = {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3}


def _unwrap(value: Any, label: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    if value is None:
        return "missing", None, f"{label} output was not provided"
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return "missing", None, f"{label} output was empty"
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            return "malformed", None, f"{label} output was not valid JSON"
    if not isinstance(value, dict):
        return "malformed", None, f"{label} output must be an object"
    if "status" in value and ("result" in value or value.get("status") != "ok"):
        status = str(value.get("status") or "failed").lower()
        inner = value.get("result")
        if status != "ok" or not isinstance(inner, dict):
            return (
                "failed" if status == "failed" else "malformed",
                inner if isinstance(inner, dict) else None,
                coerce.as_text(value.get("error"), default=f"{label} did not succeed", max_length=400),
            )
        return "ok", inner, None
    if any(key in value for key in ("risk_score", "visual_risk_score", "language_risk_score", "findings", "explanation")):
        return "ok", value, None
    return "malformed", None, f"{label} output was missing a specialist result"


def _score(result: Optional[Dict[str, Any]], aliases: Tuple[str, ...]) -> float:
    if not isinstance(result, dict):
        return 0.0
    for field in aliases:
        value = result.get(field)
        if isinstance(value, (int, float)) and value == value:
            return float(max(0.0, min(100.0, value)))
    return 0.0


def _optional_score(result: Optional[Dict[str, Any]], aliases: Tuple[str, ...]) -> Optional[float]:
    if not isinstance(result, dict):
        return None
    for field in aliases:
        value = result.get(field)
        if isinstance(value, (int, float)) and value == value:
            return float(max(0.0, min(100.0, value)))
    return None


def _indicators(result: Optional[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    items: List[Dict[str, Any]] = []
    findings = list(result.get("findings") or [])
    if source == "visual_evidence":
        findings.extend(result.get("cross_image_findings") or [])
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        description = coerce.as_text(finding.get("description"), max_length=300)
        if not description:
            continue
        items.append(
            {
                "code": coerce.as_text(finding.get("category"), default="OTHER", max_length=60),
                "severity": _SEVERITY.get(str(finding.get("severity") or "").upper(), 0.3),
                "source": source,
                "description": description,
            }
        )
    return items


def packets_to_input(
    visual_output: Any,
    claim_output: Any,
    *,
    claim_id: str = "",
    customer_id: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    visual_status, visual, visual_error = _unwrap(visual_output, "visual")
    claim_status, claim, claim_error = _unwrap(claim_output, "claim")
    resolved_id = (
        claim_id
        or (visual or {}).get("claim_id")
        or (claim or {}).get("claim_id")
        or "UNKNOWN"
    )
    indicators = _indicators(visual, "visual_evidence") + _indicators(claim, "claim_intelligence")
    if visual_status != "ok":
        indicators.append(
            {
                "code": "VISUAL_UNAVAILABLE",
                "severity": 0.5,
                "source": "visual_evidence",
                "description": visual_error or "Visual agent unavailable",
            }
        )
    if claim_status != "ok":
        indicators.append(
            {
                "code": "CLAIM_UNAVAILABLE",
                "severity": 0.5,
                "source": "claim_intelligence",
                "description": claim_error or "Claim agent unavailable",
            }
        )
    return {
        "claim_id": str(resolved_id),
        "customer_id": customer_id,
        "visual_evidence_score": _score(visual, ("risk_score", "visual_risk_score")),
        "claim_intelligence_score": _score(claim, ("risk_score", "language_risk_score")),
        "visual_evidence_summary": coerce.as_text(
            (visual or {}).get("explanation"), max_length=800
        ),
        "claim_intelligence_summary": coerce.as_text(
            (claim or {}).get("explanation"), max_length=800
        ),
        "visual_confidence": _optional_score(visual, ("confidence_score",)),
        "claim_confidence": _optional_score(claim, ("confidence_score",)),
        "description": description,
        "indicators": indicators,
        "metadata": {
            "visual_status": visual_status,
            "claim_status": claim_status,
            "visual_recommendation": (visual or {}).get("recommendation"),
            "claim_recommendation": (claim or {}).get("recommendation"),
        },
    }


def run_from_agents(
    visual_output: Any,
    claim_output: Any,
    *,
    claim_id: str = "",
    customer_id: Optional[str] = None,
    description: str = "",
    use_bedrock: Optional[bool] = None,
) -> Dict[str, Any]:
    """The connection point: Agent 1 + Agent 2 → Agent 6."""
    payload = packets_to_input(
        visual_output,
        claim_output,
        claim_id=claim_id,
        customer_id=customer_id,
        description=description,
    )
    return run(payload, use_bedrock=use_bedrock)
