def visual_evidence_stub(claim_id):
    return {
        "claim_id": claim_id,
        "risk_score": 92,
        "signals": ["ai_generated_image", "missing_exif", "synthetic_crack_pattern"],
        "confidence": 0.94,
        "recommendation": "escalate",
        "explanation": "Image shows synthetic artifacts typical of AI generation. No camera metadata found."
    }

def claim_intelligence_stub(claim_id):
    return {
        "claim_id": claim_id,
        "risk_score": 85,
        "signals": ["pressure_tactics", "emotional_manipulation", "urgency_keywords"],
        "confidence": 0.88,
        "recommendation": "escalate",
        "explanation": "Text matches known fraud scripts with high-pressure urgency tactics."
    }
