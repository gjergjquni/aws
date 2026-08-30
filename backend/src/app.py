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


def lambda_handler(event, context):
    path = event.get("path", "")
    method = event.get("httpMethod", "")
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
            claim_id = path.split("/")[-1]
            return handle_get(claim_id)
        elif path == "/claims" and method == "GET":
            params = event.get("queryStringParameters") or {}
            if "customer_id" in params:
                return handle_list_by_customer(params["customer_id"])
            return respond(400, {"error": "customer_id query param required"})
        elif path == "/uploads" and method == "POST":
            return handle_upload(event)
        # Proxy endpoints: forward to the Agent API with the x-api-key
        # attached server-side so the browser never holds the key.
        elif path == "/analyze" and method == "POST":
            status, body = proxy_request("POST", "/analyze", json.loads(event.get("body") or "{}"))
            return respond(status, body)
        elif path.startswith("/analyze/") and method == "GET":
            case_id = path.split("/")[-1]
            status, body = proxy_request("GET", f"/analyze/{case_id}")
            return respond(status, body)
        elif path == "/reviews/pending" and method == "GET":
            status, body = proxy_request("GET", "/reviews/pending")
            return respond(status, body)
        elif path.startswith("/reviews/") and path.endswith("/decision") and method == "POST":
            case_id = path.split("/")[2]
            status, body = proxy_request("POST", f"/reviews/{case_id}/decision", json.loads(event.get("body") or "{}"))
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
    case_id = submit.get("case_id", claim_id)
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
    resp = table.get_item(Key={"claim_id": claim_id})
    item = resp.get("Item")
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
