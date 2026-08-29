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
