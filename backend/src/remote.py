import json
import urllib.request
from stubs import visual_evidence_stub, claim_intelligence_stub
from adapters import adapt_visual, adapt_claim_intel

def call_visual_agent(claim_id, payload, endpoint_url):
    if not endpoint_url:
        return {"source": "stub", **visual_evidence_stub(claim_id)}
    
    visual_payload = {
        "claim_id": claim_id,
        "s3_image_url": payload.get("s3_image_url", ""),
        "product_category": payload.get("product_category", ""),
        "customer_claimed_condition": payload.get("customer_text", "")
    }
    
    data = json.dumps(visual_payload).encode()
    req = urllib.request.Request(endpoint_url, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    raw = json.loads(resp.read())
    return {"source": "live", **adapt_visual(raw)}

def call_claim_agent(claim_id, payload, endpoint_url):
    if not endpoint_url:
        return {"source": "stub", **claim_intelligence_stub(claim_id)}
    
    claim_payload = {
        "claim_id": claim_id,
        "customer_text": payload.get("customer_text", ""),
        "product_category": payload.get("product_category", ""),
        "order_value_usd": payload.get("order_value_usd", 0)
    }
    
    data = json.dumps(claim_payload).encode()
    req = urllib.request.Request(endpoint_url, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    raw = json.loads(resp.read())
    return {"source": "live", **adapt_claim_intel(raw)}

def call_orchestrator_agent(claim_id, agents, endpoint_url):
    if not endpoint_url:
        # Stub — llogarit score-in derisa Jeta të deployojë Agent 6
        vis_score = agents.get("visual_evidence", {}).get("risk_score", 0)
        clm_score = agents.get("claim_intelligence", {}).get("risk_score", 0)
        final_score = round(vis_score * 0.6 + clm_score * 0.4, 1)
        if final_score >= 70:
            recommendation = "escalate"
        elif final_score >= 40:
            recommendation = "review"
        else:
            recommendation = "approve"
        return {
            "source": "stub",
            "final_score": final_score,
            "recommendation": recommendation,
            "explanation": f"Risk score {final_score}/100 based on visual ({vis_score}) and claim ({clm_score}) analysis."
        }

    orchestrator_payload = {
        "claim_id": claim_id,
        "visual_evidence": agents.get("visual_evidence", {}),
        "claim_intelligence": agents.get("claim_intelligence", {})
    }
    data = json.dumps(orchestrator_payload).encode()
    req = urllib.request.Request(endpoint_url, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=30)
    return {"source": "live", **json.loads(resp.read())}
