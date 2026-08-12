WEIGHTS = {"visual_evidence": 0.6, "claim_intelligence": 0.4}
THRESHOLDS = {"escalate": 70, "review": 40}

def aggregate(agent_scores: dict) -> dict:
    active = {k: v for k, v in agent_scores.items() if k in WEIGHTS}
    total_weight = sum(WEIGHTS[k] for k in active)
    score = round(sum(active[k] * WEIGHTS[k] for k in active) / total_weight)
    if score >= THRESHOLDS["escalate"]:
        recommendation = "escalate"
    elif score >= THRESHOLDS["review"]:
        recommendation = "review"
    else:
        recommendation = "approve"
    return {"final_score": score, "recommendation": recommendation, "weights_used": {k: WEIGHTS[k] for k in active}}
