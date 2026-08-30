"""How the rest of the application should call these agents.

Live AWS path:

    POST /analyze or POST /claims
      -> Agent 1 (visual) + Agent 3 (claim intelligence) in parallel
      -> Agent 6 final decision
      -> automatic response, or DynamoDB pending review

After both specialists finish you can also call ``combine_agents`` directly:

    from pipeline import combine_agents

    decision = combine_agents(visual_output, claim_output, claim_id="ORDER-1")
    # decision["decision"]      FRAUD | NOT_FRAUD | HUMAN_REVIEW
    # decision["confidence"]    0-1, auto-decide at >= 0.80
    # decision["reason"]        why, including ambiguity
    # decision["final_score"]   60% visual + 40% claim, computed before any LLM

``visual_output`` / ``claim_output`` can be the inner result dicts or the Lambda
wrappers ``{"status": "ok", "result": {...}}``.

Agent 6 does not write DynamoDB. The backend orchestrator does.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from agent6 import public_decision, run_from_agents
from shared.finalize import persist_decision, run_agent6


def combine_agents(
    visual_output: Any,
    claim_output: Any,
    *,
    claim_id: str = "",
    customer_id: Optional[str] = None,
    description: str = "",
    use_bedrock: Optional[bool] = None,
) -> Dict[str, Any]:
    """Combine Agent 1 (visual) and Agent 3 (claim) into the Agent 6 decision."""
    return run_from_agents(
        visual_output,
        claim_output,
        claim_id=claim_id,
        customer_id=customer_id,
        description=description,
        use_bedrock=use_bedrock,
    )


def public_result(agent6_result: Dict[str, Any], *, case_id: str = "") -> Dict[str, Any]:
    """Frontend-facing subset of an Agent 6 result."""
    return public_decision(agent6_result, case_id=case_id)


__all__ = [
    "combine_agents",
    "public_result",
    "persist_decision",
    "run_agent6",
]
