import json
import os
import uuid
import boto3
from datetime import datetime, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

from scoring import aggregate
from remote import call_visual_agent, call_claim_agent
from explain import generate_explanation

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
table = dynamodb.Table(os.environ["TABLE_NAME"])

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError

def respond(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}, "body": json.dumps(body, default=decimal_default)}

def lambda_handler(event, context):
    path = event.get("path", "")
    method = event.get("httpMethod", "")
    try:
        if path == "/claims" and method == "POST":
            return handle_submit(event)
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
    visual_url = os.environ.get("VISUAL_EVIDENCE_URL", "")
    claim_url = os.environ.get("CLAIM_INTELLIGENCE_URL", "")
    model_id = os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0")

    with ThreadPoolExecutor(max_workers=2) as pool:
        vis_future = pool.submit(call_visual_agent, claim_id, body, visual_url)
        clm_future = pool.submit(call_claim_agent, claim_id, body, claim_url)
        vis = vis_future.result()
        clm = clm_future.result()

    agents = {"visual_evidence": vis, "claim_intelligence": clm}
    scores = {"visual_evidence": vis["risk_score"], "claim_intelligence": clm["risk_score"]}
    result = aggregate(scores)

    try:
        explanation = generate_explanation(result["final_score"], result["recommendation"], agents, model_id)
    except Exception as e:
        explanation = f"Explanation unavailable: {e}"

    item = {
        "claim_id": claim_id,
        "customer_id": body.get("customer_id", "unknown"),
        "created_at": now,
        "status": result["recommendation"],
        "final_score": result["final_score"],
        "agents": agents,
        "scores": scores,
        "weights": result["weights_used"],
        "explanation": explanation,
        "original_request": body
    }
    table.put_item(Item=json.loads(json.dumps(item), parse_float=Decimal))
    return respond(200, item)

def handle_get(claim_id):
    resp = table.get_item(Key={"claim_id": claim_id})
    item = resp.get("Item")
    if not item:
        return respond(404, {"error": "claim not found"})
    return respond(200, item)

def handle_list_by_customer(customer_id):
    resp = table.query(IndexName="customer-index", KeyConditionExpression=boto3.dynamodb.conditions.Key("customer_id").eq(customer_id))
    return respond(200, {"claims": resp["Items"]})

def handle_upload(event):
    body = json.loads(event.get("body", "{}"))
    claim_id = body.get("claim_id", str(uuid.uuid4()))
    key = f"evidence/{claim_id}/{uuid.uuid4()}.jpg"
    url = s3.generate_presigned_url("put_object", Params={"Bucket": os.environ["BUCKET_NAME"], "Key": key, "ContentType": "image/jpeg"}, ExpiresIn=300)
    return respond(200, {"upload_url": url, "s3_key": key})
