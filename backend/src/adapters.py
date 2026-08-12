def adapt_visual(raw: dict) -> dict:
    return {
        "claim_id": raw.get("claim_id"),
        "risk_score": raw.get("visual_risk_score", raw.get("risk_score", 0)),
        "signals": raw.get("metadata_problems", raw.get("signals", [])),
        "confidence": raw.get("ai_generated_confidence", raw.get("confidence", 0)),
        "recommendation": raw.get("recommendation", "review"),
        "explanation": raw.get("explanation", "")
    }

def adapt_claim_intel(raw: dict) -> dict:
    return {
        "claim_id": raw.get("claim_id"),
        "risk_score": raw.get("language_risk_score", raw.get("risk_score", 0)),
        "signals": raw.get("matched_fraud_patterns", raw.get("signals", [])),
        "confidence": raw.get("confidence", 0),
        "recommendation": raw.get("recommendation", "review"),
        "explanation": raw.get("explanation", "")
    }
