"""Aegis Swarm — Agent 6 Orchestrator (from Agjenti6).

Takes Visual (Agent 1) and Claim Intelligence (Agent 3 in the product naming;
implemented here as Agent 2) outputs, scores 60/40 before any LLM call, then
applies the 80% confidence rule to auto-decide FRAUD / NOT_FRAUD or send the
case to human review.

    from agent6 import run, run_from_agents

    result = run_from_agents(visual_output, claim_output)
    # result["decision"], result["confidence"], result["reason"]
    # result["requires_human_review"]

Reasoning lives here. DynamoDB persistence is the backend orchestrator's job.
"""

from .adapter import run_from_agents
from .models import public_decision
from .orchestrator import run
from .scoring import compute_final_score, decide, recommend

__all__ = [
    "run",
    "run_from_agents",
    "compute_final_score",
    "recommend",
    "decide",
    "public_decision",
]
__version__ = "1.1.0"
