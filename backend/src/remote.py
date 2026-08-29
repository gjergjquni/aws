import json
import os
import time
import urllib.request
from urllib.error import HTTPError

# The Agent API key lives ONLY in the backend environment (SAM parameter
# AegisApiKey -> env AEGIS_API_KEY). Never hardcode or commit it.
JETA_BASE_URL = os.environ.get(
    "AEGIS_API_URL",
    "https://xrx4q1jq0k.execute-api.us-east-1.amazonaws.com/prod",
)
JETA_API_KEY = os.environ.get("AEGIS_API_KEY", "")

def _headers():
    return {"Content-Type": "application/json", "x-api-key": JETA_API_KEY}

def _post(url, payload):
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers=_headers())
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())

def _get(url):
    req  = urllib.request.Request(url, headers=_headers())
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())

def proxy_request(method, path, payload=None):
    """Forward a request to the Agent API and return (status_code, body).

    Used by the /analyze and /reviews proxy endpoints so the frontend can
    talk to the Agent API without ever holding the x-api-key.
    """
    url = f"{JETA_BASE_URL}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return resp.getcode(), json.loads(resp.read())
    except HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {"error": {"code": "upstream_error", "message": str(e)}}
        return e.code, body

def call_jeta_orchestrator(claim_id, payload, endpoint_url):
    if not endpoint_url:
        # Stub
        return {
            "source":               "stub",
            "decision":             "HUMAN_REVIEW",
            "confidence":           0.89,
            "reason":               "Stub: score 89.2/100",
            "case_id":              claim_id,
            "requires_human_review": True,
            "final_score":          89.2
        }

    # Hapi 1 — Submit te Jeta
    jeta_payload = {
        "message": payload.get("customer_text", ""),
        "s3_url":  f"s3://aws-s3-877791042657-us-east-1-an/{payload.get('s3_image_url', 'uploads/placeholder.jpg')}",
        "case_id": claim_id,
        "product_category": payload.get("product_category", "other"),
        "order_value_usd":  payload.get("order_value_usd", 0)
    }

    submit = _post(f"{JETA_BASE_URL}/analyze", jeta_payload)
    case_id = submit.get("case_id", claim_id)

    # Hapi 2 — Poll derisa të kryhet
    for _ in range(25):  # max ~50 sekonda
        time.sleep(2)
        result = _get(f"{JETA_BASE_URL}/analyze/{case_id}")
        status = result.get("status", "processing")
        if status != "processing":
            result["case_id"] = case_id
            return result

    # Timeout
    return {
        "source":               "timeout",
        "decision":             "HUMAN_REVIEW",
        "confidence":           0,
        "reason":               "Orchestrator timeout — sent to human review",
        "case_id":              case_id,
        "requires_human_review": True
    }
