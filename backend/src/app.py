import json
import os
import uuid
import boto3
from datetime import datetime, timezone
from decimal import Decimal
from remote import call_jeta_orchestrator

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
        else:
            return respond(404, {"error": "not found"})
    except Exception as e:
        return respond(500, {"error": str(e)})

def handle_submit(event):
    body = json.loads(event.get("body", "{}"))
    claim_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    orchestrator_url = os.environ.get("ORCHESTRATOR_URL", "")

    result = call_jeta_orchestrator(claim_id, body, orchestrator_url)

    decision   = result.get("decision", "HUMAN_REVIEW")
    confidence = result.get("confidence", 0)
    reason     = result.get("reason", result.get("explanation", ""))
    case_id    = result.get("case_id", claim_id)

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
        "claim_id":              claim_id,
        "case_id":               case_id,
        "customer_id":           body.get("customer_id", "unknown"),
        "created_at":            now,
        "status":                status,
        "decision":              decision,
        "confidence":            confidence,
        "explanation":           reason,
        "requires_human_review": requires_human,
        "orchestrator_result":   result,
        "original_request":      body,
    }

    table.put_item(Item=json.loads(json.dumps(item), parse_float=Decimal))
    return respond(200, item)

def handle_decision(event, claim_id):
    body = json.loads(event.get("body", "{}"))
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
    body = json.loads(event.get("body", "{}"))
    claim_id = body.get("claim_id", str(uuid.uuid4()))
    key = f"evidence/{claim_id}/{uuid.uuid4()}.jpg"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": os.environ["BUCKET_NAME"], "Key": key, "ContentType": "image/jpeg"},
        ExpiresIn=300
    )
    return respond(200, {"upload_url": url, "s3_key": key})
