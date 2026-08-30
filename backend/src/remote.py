import json
import os
from urllib.error import HTTPError
import urllib.request

from evidence import log_event

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
    req = urllib.request.Request(url, data=data, headers=_headers())
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def _get(url):
    req = urllib.request.Request(url, headers=_headers())
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


def build_aegis_payload(claim_id: str, payload: dict, s3_url: str) -> dict:
    """Build the Agent API body using the exact s3_url of the uploaded object.

    The key is never reconstructed. Whatever s3_url was generated at upload
    time is what Agent 1 will download.
    """
    message = payload.get("customer_text") or payload.get("message") or ""
    body = {
        "claim_id": claim_id,
        "s3_url": s3_url,
        "message": message,
    }
    if payload.get("product_category"):
        body["product_category"] = payload["product_category"]
    if payload.get("order_value_usd") is not None:
        body["order_value_usd"] = payload["order_value_usd"]
    if payload.get("customer_claimed_condition"):
        body["customer_claimed_condition"] = payload["customer_claimed_condition"]
    return body


def submit_claim_to_aegis(claim_id: str, payload: dict, s3_url: str) -> tuple[dict, dict]:
    if not JETA_API_KEY:
        raise RuntimeError("AEGIS_API_KEY is not configured")

    aegis_body = build_aegis_payload(claim_id, payload, s3_url)
    log_event(
        "AEGIS_CLAIM_SUBMISSION_STARTED",
        claim_id=claim_id,
        s3_url=s3_url,
    )
    submit = _post(f"{JETA_BASE_URL}/analyze", aegis_body)
    log_event(
        "AEGIS_CLAIM_SUBMISSION_SUCCESS",
        claim_id=claim_id,
        case_id=submit.get("case_id", claim_id),
        s3_url=s3_url,
    )
    return submit, aegis_body
