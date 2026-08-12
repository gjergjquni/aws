# Aegis Backend

AI-powered return fraud detection system built on AWS serverless.

## Architecture

- **API Gateway** — single entry point for all requests
- **Lambda** — orchestrator that coordinates agents, calculates scores, generates explanations
- **DynamoDB** — stores claims with full audit trail
- **S3** — stores uploaded evidence images via presigned URLs
- **Amazon Nova Pro** — generates investigation summaries (never decides the score)

## How It Works

1. Frontend sends a claim to `POST /claims`
2. Orchestrator calls Agent 1 (Visual Evidence) and Agent 3 (Claim Intelligence) **in parallel**
3. Each agent returns a risk score (0-100) and signals
4. **Deterministic Python code** calculates the final score: `visual × 60% + language × 40%`
5. Nova Pro writes a natural-language explanation using the already-fixed score
6. Result is saved to DynamoDB and returned to the frontend

The LLM explains the decision but cannot alter the score. This makes the audit trail reproducible and contradiction structurally impossible.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/claims` | Submit a claim for fraud analysis |
| GET | `/claims/{claim_id}` | Get a specific claim |
| GET | `/claims?customer_id=X` | Get all claims for a customer |
| POST | `/uploads` | Get presigned S3 URL for image upload |

## Live API

**Base URL:** `https://q7phgdg1m5.execute-api.us-east-1.amazonaws.com/Prod`

**Swagger UI:** [Try it live](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/gjergjquni/aws/backend/backend/docs/swagger.yaml)

## Example Request

```bash
curl -X POST https://q7phgdg1m5.execute-api.us-east-1.amazonaws.com/Prod/claims \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-001",
    "product_category": "electronics",
    "order_value_usd": 999,
    "customer_text": "I received this broken laptop yesterday. I need a refund immediately."
  }'
```

**Response:** `final_score: 89, recommendation: escalate`

## Agent Contract

Each agent must return:

```json
{
  "claim_id": "string",
  "risk_score": 0-100,
  "signals": ["list", "of", "indicators"],
  "confidence": 0.0-1.0,
  "recommendation": "clear | review | escalate",
  "explanation": "string"
}
```

## Stub System

Agents currently run as stubs returning fixed demo scores (92 and 85). When live agent endpoints are ready, redeploy with:

```bash
sam deploy --parameter-overrides VisualEvidenceUrl=<url> ClaimIntelligenceUrl=<url>
```

No code changes needed — stubs switch to live automatically.

## Scoring Logic

- Visual Evidence weight: 60%
- Claim Intelligence weight: 40%
- Score >= 70 → ESCALATE
- Score >= 40 → REVIEW
- Score < 40 → APPROVE

## Tech Stack

- AWS SAM (infrastructure as code)
- Python 3.13
- Lambda, API Gateway, DynamoDB, S3
- Amazon Bedrock (Nova Pro)

## Deploy

```bash
sam build
sam deploy --guided
```
