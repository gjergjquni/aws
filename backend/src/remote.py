import json
import urllib.request
from stubs import visual_evidence_stub, claim_intelligence_stub
from adapters import adapt_visual, adapt_claim_intel

def call_visual_agent(claim_id, payload, endpoint_url):
    if not endpoint_url:
        return {"source": "stub", **visual_evidence_stub(claim_id)}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint_url, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    raw = json.loads(resp.read())
    return {"source": "live", **adapt_visual(raw)}

def call_claim_agent(claim_id, payload, endpoint_url):
    if not endpoint_url:
        return {"source": "stub", **claim_intelligence_stub(claim_id)}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint_url, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    raw = json.loads(resp.read())
    return {"source": "live", **adapt_claim_intel(raw)}
