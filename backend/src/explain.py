import json
import boto3

bedrock = boto3.client("bedrock-runtime")

def generate_explanation(score, recommendation, agents, model_id):
    prompt = f"""You are a fraud investigation assistant. Summarize this finding:
Final risk score: {score}/100
Recommendation: {recommendation}
Visual Evidence Agent: score {agents['visual_evidence']['risk_score']}, signals: {agents['visual_evidence']['signals']}
Claim Intelligence Agent: score {agents['claim_intelligence']['risk_score']}, signals: {agents['claim_intelligence']['signals']}
Write 2-3 sentences for a human investigator. Be specific about why this claim is suspicious."""

    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 300, "temperature": 0.2}
    })
    resp = bedrock.invoke_model(modelId=model_id, contentType="application/json", accept="application/json", body=body)
    result = json.loads(resp["body"].read())
    return result["output"]["message"]["content"][0]["text"]
