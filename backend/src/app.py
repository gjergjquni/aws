import json
import os
import boto3
from datetime import datetime, timezone
from urllib.error import HTTPError
from decimal import Decimal
from evidence import (
    EvidenceError,
    create_presigned_upload,
    log_event,
    resolve_evidence_location,
    sanitize_claim_id,
    verify_uploaded_object,
)
from remote import proxy_request, submit_claim_to_aegis

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
        },
        "body": json.dumps(body, default=decimal_default)
    }


def upload_bucket() -> str:
    return os.environ.get("UPLOAD_BUCKET") or os.environ["BUCKET_NAME"]


def upload_prefix() -> str:
    return os.environ.get("UPLOAD_PREFIX", "uploads")


def request_path(event):
    path = event.get("path") or event.get("rawPath") or ""
    stage = (event.get("requestContext") or {}).get("stage")
    if stage and path.startswith(f"/{stage}/"):
        path = path[len(stage) + 1 :]
    elif path.startswith("/Prod/"):
        path = path[5:]
    if path and not path.startswith("/"):
        path = "/" + path
    return path


def request_method(event):
    return (
        event.get("httpMethod")
        or ((event.get("requestContext") or {}).get("http") or {}).get("method")
        or ""
    )


def lookup_claim(case_id):
    """Find a claim by DynamoDB key (claim_id) or by stored Aegis case_id."""
    if not case_id:
        return None
    item = table.get_item(Key={"claim_id": case_id}).get("Item")
    if item:
        return item
    scanned = table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("case_id").eq(case_id)
    )
    items = scanned.get("Items") or []
    return items[0] if items else None


def claim_to_status(item):
    """Shape a DynamoDB claim as GET /analyze/{id} for the frontend."""
    orch = item.get("orchestrator_result") or {}
    if not isinstance(orch, dict):
        orch = {}
    orch_status = orch.get("status")
    stored = item.get("status")
    decision = item.get("decision") or orch.get("decision")

    if orch_status in ("processing", "completed", "pending_human_review", "failed"):
        status = orch_status
    elif stored == "pending" or item.get("requires_human_review"):
        status = "pending_human_review"
    elif stored in ("approved", "rejected") or decision in ("FRAUD", "NOT_FRAUD"):
        status = "completed"
    else:
        status = "processing"

    case_id = item.get("case_id") or item.get("claim_id")
    return {
        "status": status,
        "case_id": case_id,
        "claim_id": item.get("claim_id"),
        "decision": decision,
        "confidence": item.get("confidence") if item.get("confidence") is not None else orch.get("confidence"),
        "reason": item.get("explanation") or orch.get("reason") or orch.get("message") or "",
        "requires_human_review": bool(item.get("requires_human_review")),
        "human_decision": item.get("human_decision") or orch.get("human_decision"),
        "message": orch.get("message") or item.get("explanation") or "Claim loaded from registry",
        "poll_url": f"/analyze/{case_id}",
    }


def claim_to_review(item):
    orch = item.get("orchestrator_result") or {}
    if not isinstance(orch, dict):
        orch = {}
    return {
        "case_id": item.get("case_id") or item.get("claim_id"),
        "status": item.get("status") or orch.get("status"),
        "message": item.get("explanation") or orch.get("message") or orch.get("reason"),
        "s3_url": item.get("s3_url"),
        "confidence": item.get("confidence") if item.get("confidence") is not None else orch.get("confidence"),
        "reason": item.get("explanation") or orch.get("reason"),
        "created_at": item.get("created_at"),
        "human_decision": item.get("human_decision"),
        "agent_6_result": orch or None,
    }


def handle_analyze_get(case_id):
    status, body = proxy_request("GET", f"/analyze/{case_id}")
    if status == 200:
        return respond(status, body)
    item = lookup_claim(case_id)
    if item:
        log_event(
            "ANALYZE_FALLBACK_REGISTRY",
            case_id=case_id,
            upstream_status=status,
            claim_id=item.get("claim_id"),
        )
        return respond(200, claim_to_status(item))
    return respond(status, body if isinstance(body, dict) else {"error": "not found"})


def handle_reviews_pending():
    status, body = proxy_request("GET", "/reviews/pending")
    cases = body.get("cases") if isinstance(body, dict) else None
    if status == 200 and cases:
        return respond(status, body)
    resp = table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("status").eq("pending")
    )
    mapped = [claim_to_review(item) for item in resp.get("Items", [])]
    if mapped:
        return respond(200, {"status": "ok", "count": len(mapped), "cases": mapped})
    if status == 200:
        return respond(status, body if isinstance(body, dict) else {"status": "ok", "count": 0, "cases": []})
    return respond(status, body if isinstance(body, dict) else {"error": "not found"})


def lambda_handler(event, context):
    path = request_path(event)
    method = request_method(event)
    params = event.get("pathParameters") or {}
    try:
        if method == "OPTIONS":
            return respond(200, {})
        elif path == "/claims" and method == "POST":
            return handle_submit(event)
        elif path.startswith("/claims/") and path.endswith("/decision") and method == "PATCH":
            claim_id = path.split("/")[2]
            return handle_decision(event, claim_id)
        elif path == "/claims/pending" and method == "GET":
            return handle_list_pending()
        elif path.startswith("/claims/") and method == "GET":
            claim_id = params.get("claim_id") or path.split("/")[-1]
            return handle_get(claim_id)
        elif path == "/claims" and method == "GET":
            query = event.get("queryStringParameters") or {}
            if "customer_id" in query:
                return handle_list_by_customer(query["customer_id"])
            return respond(400, {"error": "customer_id query param required"})
        elif path == "/uploads" and method == "POST":
            return handle_upload(event)
        elif path == "/analyze" and method == "POST":
            status, body = proxy_request("POST", "/analyze", json.loads(event.get("body") or "{}"))
            return respond(status, body)
        elif path.startswith("/analyze/") and method == "GET":
            case_id = params.get("case_id") or path.split("/")[-1]
            return handle_analyze_get(case_id)
        elif path == "/reviews/pending" and method == "GET":
            return handle_reviews_pending()
        elif path.startswith("/reviews/") and path.endswith("/decision") and method == "POST":
            case_id = params.get("case_id") or path.split("/")[2]
            status, body = proxy_request(
                "POST",
                f"/reviews/{case_id}/decision",
                json.loads(event.get("body") or "{}"),
            )
            return respond(status, body)
        else:
            return respond(404, {"error": "not found"})
    except EvidenceError as e:
        return respond(e.status, e.as_body())
    except Exception as e:
        return respond(500, {"error": {"code": "internal_error", "message": str(e)}})


def handle_submit(event):
    body = json.loads(event.get("body") or "{}")
    claim_id = sanitize_claim_id(body.get("claim_id"))
    now = datetime.now(timezone.utc).isoformat()
    bucket = upload_bucket()

    evidence_bucket, evidence_key, s3_url = resolve_evidence_location(body, bucket)
    verified = verify_uploaded_object(
        s3,
        evidence_bucket,
        evidence_key,
        expected_content_type=body.get("content_type"),
    )
    log_event(
        "UPLOAD_SUCCESS",
        claim_id=claim_id,
        bucket=verified["bucket"],
        key=verified["key"],
        content_type=verified["content_type"],
        content_length=verified["content_length"],
    )

    try:
        submit, aegis_body = submit_claim_to_aegis(claim_id, body, s3_url)
    except HTTPError as exc:
        try:
            upstream = json.loads(exc.read())
        except Exception:
            upstream = {"error": {"code": "upstream_error", "message": str(exc)}}
        return respond(exc.code, upstream)
    except RuntimeError as exc:
        return respond(503, {"error": {"code": "aegis_unconfigured", "message": str(exc)}})
    case_id = submit.get("case_id") or submit.get("id") or submit.get("caseId") or claim_id
    decision = submit.get("decision", "HUMAN_REVIEW")
    confidence = submit.get("confidence", 0)
    reason = submit.get("reason", submit.get("explanation", submit.get("message", "")))

    if decision == "FRAUD":
        status = "rejected"
        requires_human = False
    elif decision == "NOT_FRAUD":
        status = "approved"
        requires_human = False
    else:
        status = "pending"
        requires_human = True

    item = {
        "claim_id": claim_id,
        "case_id": case_id,
        "customer_id": body.get("customer_id", "unknown"),
        "created_at": now,
        "status": status,
        "decision": decision,
        "confidence": confidence,
        "explanation": reason,
        "requires_human_review": requires_human,
        "s3_url": s3_url,
        "s3_key": evidence_key,
        "evidence": {
            "bucket": evidence_bucket,
            "key": evidence_key,
            "content_type": verified["content_type"],
            "content_length": verified["content_length"],
        },
        "aegis_request": aegis_body,
        "orchestrator_result": submit,
        "original_request": body,
    }

    table.put_item(Item=json.loads(json.dumps(item), parse_float=Decimal))
    return respond(202, {
        "status": submit.get("status", "processing"),
        "claim_id": claim_id,
        "case_id": case_id,
        "poll_url": submit.get("poll_url", f"/analyze/{case_id}"),
        "s3_url": s3_url,
        "evidence": item["evidence"],
        "message": submit.get("message", "Claim accepted for analysis"),
    })


def handle_decision(event, claim_id):
    body = json.loads(event.get("body") or "{}")
    decision = body.get("decision", "")
    if decision not in ["approve", "reject", "request_info"]:
        return respond(400, {"error": "decision must be approve, reject, or request_info"})
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"claim_id": claim_id},
        UpdateExpression="SET #s = :s, decided_at = :d, decided_by = :u, requires_human_review = :f",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": decision,
            ":d": now,
            ":u": body.get("investigator_id", "unknown"),
            ":f": False
        }
    )
    return respond(200, {"claim_id": claim_id, "status": decision, "decided_at": now})


def handle_list_pending():
    resp = table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr("status").eq("pending")
    )
    return respond(200, {"claims": resp.get("Items", [])})


def handle_get(claim_id):
    item = lookup_claim(claim_id)
    if not item:
        return respond(404, {"error": "claim not found"})
    return respond(200, item)


def handle_list_by_customer(customer_id):
    resp = table.query(
        IndexName="customer-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("customer_id").eq(customer_id)
    )
    return respond(200, {"claims": resp["Items"]})


def handle_upload(event):
    body = json.loads(event.get("body") or "{}")
    ticket = create_presigned_upload(s3, body, upload_bucket(), upload_prefix())
    return respond(200, ticket)
