# Aegis Swarm — Return Fraud Detection Agents

Serverless AI agents that score e-commerce return claims for fraud. This repo is
**backend agents only**. The React frontend, the S3 evidence bucket, and the
presigned-URL upload path belong to the upload service team.

## How the rest of the app connects

**Live path (already deployed).** After a photo is in their S3 bucket:

1. `POST /claims` or `POST /analyze` with a canonical S3 URL or key (not a CloudFront/CDN URL)
2. Poll `GET /results/{claimId}` or `GET /analyze/{caseId}` until the workflow finishes

That path runs Agent 1 (photos) and Agent 3 (claim text) in parallel, then Agent 6
(60% visual + 40% claim). Intake normalizes the image reference to
`{bucket, key}` once; Agent 1 downloads with `s3:GetObject` and never HTTP-GETs
the URL.

### Exact JSON the application backend must send

`POST /claims` (all six fields required):

```json
{
  "claim_id": "CLAIM-123",
  "s3_image_url": "s3://YOUR-EVIDENCE-BUCKET/uploads/CLAIM-123.jpg",
  "product_category": "electronics",
  "customer_claimed_condition": "damaged",
  "customer_text": "The screen arrived cracked.",
  "order_value_usd": 299.99
}
```

`POST /analyze` (frontend-oriented aliases):

```json
{
  "message": "The screen arrived cracked.",
  "s3_url": "s3://YOUR-EVIDENCE-BUCKET/uploads/CLAIM-123.jpg"
}
```

Accepted image values (all become `{bucket, key}` internally):

- `s3://YOUR-EVIDENCE-BUCKET/uploads/CLAIM-123.jpg`
- `https://YOUR-EVIDENCE-BUCKET.s3.us-east-1.amazonaws.com/uploads/CLAIM-123.jpg`
- the same HTTPS URL with `?X-Amz-...` (presigned; query is discarded)
- `uploads/CLAIM-123.jpg`

Aliases for the image field: `s3_image_url`, `s3_url`, `s3_key`, `image_url`,
camelCase of those, or `evidence.url` / `evidence.key`. **Not accepted:**
CloudFront URLs, custom domains, `photo_url`, nested `imageUrl` under random
objects. Those return `EVIDENCE_MISSING` or `EVIDENCE_INVALID_URL` instead of
being ignored.

Expected S3 object:

```text
Bucket:  the EvidenceBucketName used at sam deploy
Key:     uploads/CLAIM-123.jpg
Content-Type: image/jpeg (PNG/WEBP/GIF/BMP/TIFF also work)
Size:    > 0 bytes
Format:  not HEIC/HEIF — re-encode iPhone photos to JPEG first
```

## Where the boundary is

```
   THEIR SCOPE                              │  OUR SCOPE (this repo)
                                            │
   React UI                                 │
      │                                     │
      │ 1. request presigned URL            │
      ▼                                     │
   Upload service ──2. presigned PUT──► S3  │
      │                  (their bucket)  ▲  │
      │                                  │  │        read-only
      │ 3. POST /claims ────────────────────┼──►  Intake ──┐
      │    {claim_id, s3_image_url, ...} │  │              │
      │                                  │  │              ▼
      │                                  │  │      Step Functions
      │                                  │  │      ┌──────────────┐
      │                                  └──┼──────│ Visual agent │
      │                                     │      │ Claim agent  │ (parallel)
      │                                     │      └──────┬───────┘
      │                                     │             ▼
      │ 4. GET /results/{claimId} ◄──────────┼───── Aggregator ──► DynamoDB
      │    poll until complete              │
```

**We never write to S3 and never hold S3 credentials.** Our agent Lambdas get
read-only access to one prefix of their bucket through their IAM execution roles.

## What we need from the upload service team

| # | What | Why |
|---|---|---|
| 1 | The **bucket name** | Deploy parameter `EvidenceBucketName` |
| 2 | The **key prefix** they write under | Deploy parameter `EvidenceKeyPrefix`, default `uploads/` |
| 3 | The **KMS key ARN**, if the bucket uses SSE-KMS with a customer-managed key | Deploy parameter `EvidenceKmsKeyArn`; without it our reads fail with `AccessDenied` |
| 4 | A **bucket policy** granting our roles `s3:GetObject` — only if their bucket is in a different AWS account | Cross-account S3 needs permission on both sides |

## What they need from us

The `ApiUrl` and API key value from the stack outputs, plus this contract:

- After the upload finishes, call `POST /claims` with their own `claim_id` and the
  `s3_image_url` of the object they wrote.
- Poll `GET /results/{claimId}` until `complete` is `true`.

They keep ownership of claim IDs — we don't mint them, so their system stays the
source of truth for identity.

### `s3_image_url` can be whatever form is convenient for them

All of these resolve to the same object, so nobody has to write a translation
layer on either side:

| Form | Example |
|---|---|
| `s3://` URI | `s3://bucket/uploads/order-99123.jpg` |
| Virtual-hosted URL | `https://bucket.s3.us-east-1.amazonaws.com/uploads/order-99123.jpg` |
| Path-style URL | `https://s3.us-east-1.amazonaws.com/bucket/uploads/order-99123.jpg` |
| Presigned GET URL | the same, with `?X-Amz-Signature=...` — the query string is discarded |
| Bare object key | `uploads/order-99123.jpg` |

**The URL is parsed, never fetched.** The bucket in it is compared against the
configured bucket and the request is refused if it doesn't match, so a caller
can't aim these Lambdas at an object we were never meant to read. Download then
happens through `s3:GetObject` with the execution role, which is why a presigned
URL works even after its signature has expired — and why one isn't needed at all.

**Application backend checklist**

1. Upload the file to the evidence bucket under `uploads/`.
2. Send `s3_image_url` as an S3 URL or key from the table above — not a CloudFront, CDN, or app `/images/...` URL.
3. Use JPEG or PNG (not HEIC). Size must be greater than 0.
4. Include `x-api-key`. Field names are snake_case (`s3_image_url`), not `photo_url` / `imageUrl` alone (camelCase of the documented names is accepted).
5. If Agent 1 still fails, read `error_code` (`EVIDENCE_ACCESS_DENIED`, `EVIDENCE_NOT_FOUND`, `EVIDENCE_UNSUPPORTED_FORMAT`, …) rather than a generic "cannot read image".

---

## The agents

### Agent 1 — Visual Evidence (`src/agent_visual/`)

Analyzes one or more evidence photos. It is an evidence-analysis component, not a
fraud adjudicator. It never states that a customer committed fraud or that an
image is definitely AI-generated.

Pipeline (real services when configured; never faked):

1. Resolve S3 keys (or local demo paths)
2. Validate format/size and decode with Pillow
3. Extract EXIF and flag metadata problems in code
4. Perceptual hashes for exact/near-duplicate detection
5. Amazon Rekognition `DetectLabels` / `DetectText` / `DetectModerationLabels` / `DetectFaces`
6. Optional Hive classifier (enrichment only)
7. Amazon Bedrock Nova Pro vision reasoning over **tool facts**
8. Schema validation of the model fragment
9. Deterministic risk/confidence scoring in `shared/scoring.py`

If Rekognition is denied or down, the result records
`tool_status.rekognition = unavailable` and a limitation. It does **not** invent
labels. Hive remains optional: missing key/quota reports `null`, distinct from
`0.0`.

Public fields include `risk_score`, `confidence_score`, `risk_level`, `findings`,
`cross_image_findings`, `limitations`, `explanation`, and
`recommendation` (`NO_ADDITIONAL_ACTION` | `REVIEW_EVIDENCE` |
`MANUAL_INVESTIGATION`). `visual_risk_score` is kept as an alias so the
aggregator still works.

**Metadata problems are detected in code, not asked of the model.** Reading tags
is exact work with a right answer. The model is told what was already found and
asked to weigh it.

| `metadata_problems` flag | Means |
|---|---|
| `missing_exif` | No metadata at all. Social and messaging apps strip it |
| `exif_extraction_failed` | Metadata present but unparseable |
| `no_camera_make` | No `Make` or `Model` tag |
| `no_original_timestamp` | No capture time recorded |
| `future_timestamp` | Capture time more than a day ahead of now |
| `ai_tool_in_metadata` | `Software` tag names a generator |
| `edited_in_photoshop`, `edited_in_gimp`, … | `Software` tag names a pixel editor |

An editor flag is not proof of fraud — phone cameras write their own tags — but
it tells an investigator the file has been through an editor.

### Agent 2 — Claim Intelligence (`src/agent_claim/`)

Analyzes claim language and internal consistency. It evaluates the claim text,
not the customer as a person. Grammar, spelling, and non-native writing are not
fraud signals.

Pipeline:

1. Embed the claim with Amazon Titan Text Embeddings V2
2. Retrieve similar synthetic fraud-pattern documents
   - OpenSearch k-NN when `OPENSEARCH_ENDPOINT` is set
   - otherwise in-memory cosine similarity over bundled documents (documented degraded mode)
   - lexical overlap if embeddings fail (explicitly **not** vector search)
3. Bedrock Nova Pro reasons over the claim **plus retrieved hits as tool facts**
4. Schema validation
5. Deterministic scoring

The LLM cannot invent vector-search hits. `retrieved_patterns` always come from
application retrieval. Similarity is not treated as proof of fraud.

Public fields include `risk_score`, `confidence_score`, `findings`
(categories `CONTRADICTION|TEMPLATE_SIMILARITY|URGENCY|COMPLETENESS|CONTEXT|OTHER`),
`retrieved_patterns`, `limitations`, `explanation`, and `recommendation`
(`NO_ADDITIONAL_ACTION` | `REVIEW_CLAIM` | `MANUAL_INVESTIGATION`).
`language_risk_score` is kept as an aggregator alias.

### Aggregator (`src/agent_aggregate/`) — Agent 6

Combines both specialist scores with configurable weights (default **60% visual
+ 40% claim**, env `VISUAL_WEIGHT` / `CLAIM_WEIGHT`, must sum to 1.0). The
numeric score is computed before any LLM call. Auto FRAUD / NOT_FRAUD only at
≥80% confidence (`CONFIDENCE_THRESHOLD`); otherwise HUMAN_REVIEW. Nova Pro
writes the explanation only and cannot override the score.

## Scoring (deterministic)

The LLM emits findings. Application code computes scores in `src/shared/scoring.py`.
Confidence is confidence in the **analysis** (tool availability, data completeness),
not P(fraud).

**Agent 1** — strongest finding per category; categories stack; cap 100.
Missing EXIF alone is a weak signal. A single HIGH duplicate/manipulation finding
recommends `REVIEW_EVIDENCE` even if the numeric score is still medium.

**Agent 2** — same pattern. Urgency alone cannot produce HIGH. Template similarity
from retrieval adds a bounded term; it is not proof.

## Degraded modes (explicit, never silent fakes)

| Missing piece | What happens |
|---|---|
| Rekognition denied/down | Agent 1 continues; `tool_status.rekognition=unavailable`; no labels invented |
| Hive missing | `hive_ai_score=null`, `hive_available=false` |
| OpenSearch unset | Agent 2 `retrieval_mode=IN_MEMORY` (real Titan embeddings if available) |
| Titan embeddings fail | Agent 2 `retrieval_mode=LEXICAL` + limitation "this is not vector search" |
| Bedrock JSON/schema invalid after retry | Agent returns `status=failed`; not coerced into a successful analysis |
| DynamoDB unset (local) | Results are returned but not persisted |

## Data model

## Data model

One DynamoDB table, one item per fact about a claim:

| PK | SK | Holds |
|---|---|---|
| `CLAIM#{id}` | `META` | Intake inputs, `status`, timestamps |
| `CLAIM#{id}` | `AGENT#VISUAL` | Visual agent result or failure |
| `CLAIM#{id}` | `AGENT#CLAIM` | Claim agent result or failure |
| `CLAIM#{id}` | `VERDICT` | Combined score and recommendation |

Reads are a single `Query` on `PK`, so there are no secondary indexes. Each agent
writes only its own item, so two agents finishing at once can't clobber each
other.

---

# Setup runbook

Steps 1 and 3 are on your machine, 2 and 4–7 are in the AWS console, 8–10 deploy
and verify. Every value you copy out of the console has exactly one destination,
named in the step that produces it — nothing is pasted into a file in this repo.

| What you collect | Where it goes |
|---|---|
| Access key ID + secret (step 2) | `aws configure` prompt on your machine only |
| Nothing (step 4) | Bedrock access is granted to the account, not copied |
| Hive Secret Key (step 5) | The Secrets Manager secret in step 6 |
| Bucket name (step 7) | The `EvidenceBucketName` deploy parameter in step 8 |
| API key value (step 9) | Your teammates' server-side config |

## 1. Install the tools

```powershell
python --version   # need 3.12.x
aws --version      # need 2.x
sam --version      # need 1.100+
docker --version   # must be RUNNING, not just installed
```

Missing anything: [Python 3.12](https://www.python.org/downloads/),
[AWS CLI v2](https://awscli.amazonaws.com/AWSCLIV2.msi),
[SAM CLI](https://github.com/aws/aws-sam-cli/releases/latest/download/AWS_SAM_CLI_64_PY3.msi),
[Docker Desktop](https://www.docker.com/products/docker-desktop/).

Start Docker Desktop and wait for the whale icon to settle. `sam build
--use-container` needs it to compile Pillow's Linux wheel — without Docker you get
a Pillow that imports fine on Windows and crashes in Lambda.

## 2. Create the deploy user

Console → **IAM** → **Users** → **Create user**, named `aegis-deployer`. Do not
give it console access.

Attach **`PowerUserAccess`**, then add an inline policy so CloudFormation can
create the Lambda execution roles. **Create inline policy** → JSON tab → paste,
replacing `YOUR_ACCOUNT_ID` with your 12-digit account number:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "iam:CreateRole", "iam:DeleteRole", "iam:GetRole",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:GetRolePolicy",
      "iam:AttachRolePolicy", "iam:DetachRolePolicy",
      "iam:ListRolePolicies", "iam:ListAttachedRolePolicies",
      "iam:TagRole", "iam:UntagRole", "iam:PassRole"
    ],
    "Resource": "arn:aws:iam::YOUR_ACCOUNT_ID:role/aegis-*"
  }]
}
```

Name it `AegisRoleManagement`. Scoping to `aegis-*` means this user can't touch any
IAM role outside this project — which is why **your stack name must start with
`aegis`**.

## 3. Configure credentials locally

IAM → `aegis-deployer` → **Security credentials** → **Create access key** →
**Command Line Interface (CLI)** → **Create**. The secret is shown once.

```powershell
aws configure
```

| Prompt | Value |
|---|---|
| AWS Access Key ID | your access key ID |
| AWS Secret Access Key | your secret (not echoed as you type) |
| Default region name | `us-east-1` |
| Default output format | `json` |

Verify: `aws sts get-caller-identity` should print your account and the
`aegis-deployer` ARN.

**This is the only AWS access key in the whole project**, and it exists solely so
`sam deploy` can run from your laptop. The deployed Lambdas never use keys — see
"How the Lambdas authenticate" below.

## 4. Enable Bedrock Nova Pro and Titan embeddings

Console → **Bedrock** → confirm the region selector says **N. Virginia
(us-east-1)** → **Model access** → **Modify model access** → check **Nova Pro**
and **Titan Text Embeddings V2** → **Submit**. Amazon's own models are granted in
seconds; refresh until it reads **Access granted**.

Rekognition does not need a separate model-access screen. The visual agent IAM
role is granted `rekognition:DetectLabels|DetectText|DetectModerationLabels|DetectFaces`.

Then confirm invocation works, because this is the most common place this stack
fails:

```powershell
aws bedrock-runtime converse --region us-east-1 --model-id "us.amazon.nova-pro-v1:0" --messages '[{\"role\":\"user\",\"content\":[{\"text\":\"say ok\"}]}]'
```

You should get JSON containing `ok`.

> **Why `us.amazon.nova-pro-v1:0` and not `amazon.nova-pro-v1:0`?** Nova models
> reject the bare foundation-model ID for on-demand invocation with
> `ValidationException: on-demand throughput isn't supported`. They must be called
> through a cross-region inference profile, which is the base ID with a geography
> prefix. The IAM policies here grant `bedrock:InvokeModel` on the profile **and**
> on the foundation model in all three regions the US profile can route to
> (`us-east-1`, `us-east-2`, `us-west-2`), because the profile load-balances
> across them.

## 5. Get a Hive V3 Secret Key

Agent 1 calls Hive **AI-Generated and Deepfake Content Detection** (V3):

`POST https://api.thehive.ai/api/v3/hive/ai-generated-and-deepfake-content-detection`

with `Authorization: Bearer <SECRET_KEY>` and the **downloaded image bytes**
(multipart `media`). It never sends a private S3 URL.

1. Hive dashboard → **Service API Keys** → create a key.
2. Copy the **Secret Key** (not the Access Key ID).

Hive is one signal (`ai_generated`, `deepfake`). It does not decide fraud.

## 6. Store the key in Secrets Manager

The live secret name is **`hive-api-key-1`**. Field names `api_key`, `api key`,
or `Secret Key` all work.

Lambda reads it with IAM `GetSecretValue`. Do **not** use the
`localhost:2773` Secrets Manager Agent curl from EC2/ECS install docs — that
is a different client. Never put the key in git or Lambda env vars.

## 7. Make sure an evidence bucket exists

Deploy needs a bucket name and won't proceed without one. If your teammates'
bucket already exists, get its name and key prefix from them and skip to step 8.

If it doesn't exist yet, don't wait for them — create your own and point the stack
at that. Switching to theirs later is one `sam deploy` with a different parameter,
which only rewrites two IAM policies and an environment variable.

```powershell
$acct = aws sts get-caller-identity --query Account --output text
$bucket = "aegis-evidence-$acct"
aws s3api create-bucket --bucket $bucket --region us-east-1
aws s3api put-public-access-block --bucket $bucket `
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
aws s3 cp .\test.jpg "s3://$bucket/uploads/TEST-001/smoke.jpg"
echo $bucket
```

`test.jpg` on disk is a local smoke-test file only. Production Aegis **rejects**
the reserved key `uploads/test.jpg` so a missing user photo can never be silently
replaced by a fixture. The object key you send in `s3_image_url` / `s3_url` must
be the exact uploaded object, for example `uploads/<claim_id>/<uuid>.jpg`.

Two omissions are deliberate. There's no `--create-bucket-configuration` because
us-east-1 rejects an explicit `LocationConstraint`, and no `put-bucket-encryption`
because new buckets get SSE-S3 by default — which is what you want, since it means
`EvidenceKmsKeyArn` stays empty. The account ID suffix is there because bucket
names are globally unique across all of AWS.

The upload must land under `uploads/`, matching `EvidenceKeyPrefix`. That prefix is
what the IAM read grant is scoped to, so an object outside it is unreadable by
design.

## 8. Deploy

```powershell
cd "aegis-swarm-agents"
sam build --use-container
sam deploy --guided
```

| Prompt | Answer |
|---|---|
| Stack Name | `aegis-swarm` (must start with `aegis`) |
| AWS Region | `us-east-1` |
| Parameter EvidenceBucketName | the bucket name from step 7 — required |
| Parameter EvidenceKeyPrefix | `uploads/`, or whatever prefix the uploader writes under |
| Parameter EvidenceKmsKeyArn | empty unless the bucket uses a customer-managed KMS key |
| Parameter AllowedOrigin | the frontend URL, or `*` while developing |
| Parameter HiveSecretName | `hive-api-key-1` |
| Other parameters | accept the defaults |
| Confirm changes before deploy | `y` |
| Allow SAM CLI IAM role creation | `y` |
| Disable rollback | `n` |
| Save arguments to samconfig.toml | `y` |

First build takes a few minutes while Docker pulls the build image. After this,
deploying is just `sam deploy`.

## 9. Get the API key for the upload service

The stack creates an API key and usage plan so the endpoints aren't open to the
internet spending your Bedrock budget. The `ApiKeyId` output is the key's ID, not
its value:

```powershell
aws apigateway get-api-key --api-key PASTE_ApiKeyId_HERE --include-value --region us-east-1 --query value --output text
```

Give the upload service team the `ApiUrl` output and that value, to be sent as an
`x-api-key` header. It belongs in **their** server-side config — anything in a
React bundle is public.

## 10. Run one claim end to end

With `uploads/TEST-001/smoke.jpg` in place from step 7 (do **not** send
`uploads/test.jpg` — Aegis rejects that reserved fixture key in production):

```powershell
$api = aws cloudformation describe-stacks --stack-name aegis-swarm `
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text
$keyId = aws cloudformation describe-stacks --stack-name aegis-swarm `
  --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" --output text
$key = aws apigateway get-api-key --api-key $keyId --include-value --query value --output text

$body = @{
  claim_id                   = "TEST-001"
  s3_image_url               = "s3://$bucket/uploads/TEST-001/smoke.jpg"
  product_category           = "electronics"
  customer_claimed_condition = "Screen arrived cracked"
  customer_text              = "Box was crushed in transit and the screen is shattered. I need a refund today."
  order_value_usd            = 249.99
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "$api/claims" -Headers @{ "x-api-key" = $key } `
  -ContentType "application/json" -Body $body

Start-Sleep -Seconds 15
Invoke-RestMethod -Uri "$api/results/TEST-001" -Headers @{ "x-api-key" = $key } | ConvertTo-Json -Depth 6
```

`Invoke-RestMethod` rather than `curl`, because PowerShell aliases `curl` to
`Invoke-WebRequest`, which mangles JSON bodies.

What the failures mean:

| Symptom | Cause |
|---|---|
| 400 `does not point at the configured evidence bucket` | The URL's bucket isn't `EvidenceBucketName` |
| 400 `No object found at` | Nothing at that key, or it's outside `EvidenceKeyPrefix` |
| 403 with no body | Missing or wrong `x-api-key` |
| `visual` agent `failed`, error mentions `AccessDenied` | Bucket, prefix, or KMS wiring is wrong |
| Either agent `failed`, error mentions model access | Step 4 didn't finish; re-check Bedrock model access |
| `hive_available: false` | Expected if you skipped steps 5–6; everything else still works |

## What is *not* automated

| Step | Why it can't be in the template |
|---|---|
| Bedrock model access (step 4) | Per-account, per-region console action with no CloudFormation resource |
| The Hive key value (steps 5–6) | A secret value in a template is a secret in your git history |
| The deploy IAM user (steps 2–3) | It's the identity that runs CloudFormation, so it must exist first |
| The evidence bucket (step 7) | Owned by the upload service, so this stack takes its name as a parameter and only reads from it |

Everything else — table, five functions, five IAM roles, state machine, API
Gateway, usage plan, log groups, and the fraud pattern library — is created by
`sam deploy`.

---

# How the Lambdas authenticate

Worth being explicit, because it's the most common source of confusion:

**There are no API keys or access keys in this codebase.** Two mechanisms cover
everything:

1. **AWS services (S3, DynamoDB, Bedrock, Step Functions, Secrets Manager).** Each
   Lambda has an IAM execution role created by CloudFormation. At invocation the
   Lambda runtime injects temporary credentials for that role into the
   environment, and `boto3` picks them up with no configuration. Nothing is
   stored, and the credentials rotate themselves every few hours.

2. **Hive, the only third party.** The Lambda receives the *name* of a Secrets
   Manager secret, not the secret. At runtime it calls `GetSecretValue` using its
   execution role and caches the result for the life of the container.

The consequence: to grant or revoke access you edit the IAM policy in
`template.yaml` and redeploy. There is no credential to leak, copy, or rotate.

---

# API contract

Base URL is the `ApiUrl` output. **Every request needs an `x-api-key` header**
except the CORS preflight.

## `POST /claims`

Called once the evidence photo is already in S3.

```json
{
  "claim_id": "ORDER-99123",
  "s3_image_url": "s3://your-bucket/uploads/2026/08/17/order-99123.jpg",
  "product_category": "electronics",
  "customer_claimed_condition": "Screen arrived cracked in the corner",
  "customer_text": "The box was completely empty when it arrived. I need a refund TODAY or my lawyer will be in touch.",
  "order_value_usd": 899.99
}
```

All six fields are required.

| Field | Rule |
|---|---|
| `claim_id` | 3–64 characters of letters, digits, hyphens, or underscores |
| `s3_image_url` | Any form from the table above; must resolve to the configured bucket and start with `EvidenceKeyPrefix`. `s3_key` is accepted as an alias |
| `product_category` | `electronics`, `clothing`, or `other` by convention, but any text up to 60 characters is accepted and lower-cased. Values outside the published set are logged, not rejected |
| `customer_claimed_condition` | Up to 2000 characters |
| `customer_text` | Up to `MAX_CUSTOMER_TEXT_CHARS` (default 8000) |
| `order_value_usd` | A finite number from 0 to 1,000,000 |

Intake verifies the object exists before accepting, so a claim submitted before
the upload finished returns 400 rather than failing later inside the workflow.

Response `202`:

```json
{ "claim_id": "ORDER-99123", "status": "processing", "poll_url": "/results/ORDER-99123" }
```

Resubmitting the same `claim_id` is safe — the workflow execution is named after
the claim, so a duplicate submit won't start a second billed analysis.

## `GET /results/{claimId}`

Poll every ~2 seconds until `complete` is `true`. A typical claim finishes in
15–40 seconds. While processing, agent entries fill in one at a time.

```json
{
  "claim_id": "ORDER-99123",
  "status": "complete",
  "complete": true,
  "product_category": "electronics",
  "order_value_usd": 899.99,
  "created_at": "2026-08-17T20:15:02.531000+00:00",
  "updated_at": "2026-08-17T20:15:38.114000+00:00",
  "agents": {
    "visual": {
      "status": "ok",
      "analyzed_at": "2026-08-17T20:15:31.882000+00:00",
      "error": null,
      "result": {
        "claim_id": "ORDER-99123",
        "visual_risk_score": 78,
        "image_manipulated": true,
        "ai_generated_confidence": 0.85,
        "hive_ai_score": 0.91,
        "hive_deepfake_score": 0.02,
        "hive_available": true,
        "metadata_problems": ["no_original_timestamp", "edited_in_photoshop"],
        "visual_findings": ["Crack edges have no glass displacement", "Shadow direction inconsistent"],
        "exif_data": {
          "camera": "Apple iPhone 14",
          "timestamp": null,
          "software": "Adobe Photoshop 25.1"
        },
        "explanation": "Photoshop tag with no capture time, and Hive scored 0.91 for AI generation.",
        "recommendation": "escalate"
      }
    },
    "claim": {
      "status": "ok",
      "analyzed_at": "2026-08-17T20:15:22.104000+00:00",
      "error": null,
      "result": {
        "claim_id": "ORDER-99123",
        "language_risk_score": 82,
        "contradictions_found": false,
        "matched_fraud_patterns": ["empty_box_scam"],
        "urgency_tactics": true,
        "sentiment": { "tone": "angry", "urgency": "high", "aggression": "high" },
        "explanation": "Matches the empty-box pattern on a high-value order and opens with legal threats.",
        "recommendation": "escalate"
      }
    }
  },
  "verdict": {
    "combined_risk_score": 80,
    "recommendation": "escalate",
    "degraded": false,
    "agents_succeeded": ["claim", "visual"],
    "agent_scores": { "visual": 78, "claim": 82 },
    "weights": { "visual": 0.5, "claim": 0.5 }
  }
}
```

`status` is `processing`, `complete`, or `failed`. An agent that failed has
`status: "failed"`, a populated `error`, and `result: null` — render the other
agent's findings and surface `verdict.degraded`.

Any field inside `exif_data` is `null` when the tag was absent, which is
deliberate: a string saying `"unknown"` would render as if the camera had reported
it. Likewise `hive_ai_score: null` means Hive had no opinion (no key, quota
exhausted, or API down), which is not the same as `0.0` meaning "looks real" —
check `hive_available` before showing the number.

A claim stuck in `processing` for over 15 minutes is reported as `failed` with a
`note`, so the UI never polls forever.

## Error shape

Every error uses one shape, so callers branch on `code` rather than parsing prose:

```json
{ "error": { "code": "validation_error", "message": "Missing required field: s3_image_url" } }
```

| Status | Code | Meaning |
|---|---|---|
| 400 | `validation_error` | Bad or missing input; message names the field |
| 403 | — | Missing or wrong `x-api-key` (produced by API Gateway) |
| 404 | `not_found` | No such claim |
| 409 | `conflict` | That `claim_id` already exists |
| 429 | — | Rate limit or daily quota exceeded |
| 500 | `internal_error` | Unexpected failure; check CloudWatch |
| 502 | `upstream_error` | A dependency failed |

---

# Development

## Run the offline test suite

```powershell
python local_test.py
```

Covers the Pillow pipeline, EXIF problem detection, S3 reference resolution,
input validation, schema validation, scoring policy, verdict aggregation, the
pattern library, JSON recovery, prompt-injection fencing, DynamoDB serialisation,
image forensics, Rekognition-unavailable honesty, and Agent 1 / Agent 2 / Agent 6
pipelines with **explicit test doubles** (not production fakes). No AWS credentials,
no network calls, safe for CI.

## Run the Agent 1 + Agent 2 + Agent 6 demo

```powershell
pip install -r src/requirements.txt
python demo.py
```

Without AWS credentials this prints `DEMO_MOCKED` results and says so clearly.
With credentials configured (`aws configure` or env vars):

```powershell
python demo.py --real-aws
```

That path invokes Rekognition, Bedrock, and Titan. OpenSearch is used only when
`OPENSEARCH_ENDPOINT` is set; otherwise Agent 2 reports in-memory retrieval.

Seed OpenSearch (optional, requires a real endpoint):

```powershell
$env:PYTHONPATH = "src"
python scripts/seed_opensearch.py
```

## Validate the template before deploying

```powershell
sam validate --lint
```

## Watch a claim run

```powershell
aws stepfunctions list-executions --state-machine-arn PASTE_WorkflowArn --max-items 5
sam logs --stack-name aegis-swarm --name aegis-swarm-agent-visual --tail
```

The Step Functions console shows the parallel branches graphically, which is the
fastest way to see which agent failed and why.

## Project layout

```
aegis-swarm-agents/
├── template.yaml              # SAM: API, Lambdas, DynamoDB, Step Functions
├── local_test.py              # offline tests (not deployed)
├── demo.py                    # local Agent 1 + 2 + 6 run (not deployed)
├── src/                       # what `sam build` deploys
│   ├── pipeline.py            # call combine_agents() from the rest of the app
│   ├── agent_visual/          # Agent 1 — photos
│   ├── agent_claim/           # Agent 2 — claim text
│   ├── agent6/                # Agent 6 — 60/40 score + explanation
│   ├── agent_aggregate/       # Agent 6 — 60/40 score then FRAUD/NOT_FRAUD/HUMAN_REVIEW
│   ├── api_intake/            # POST /claims
│   ├── api_results/           # GET /results/{claimId}
│   ├── config/fraud_pattern_documents.json
│   └── shared/
└── scripts/seed_opensearch.py # optional; only if you add OpenSearch
```

Deployable code lives under `src/` so `sam build` can't package `.git`, the
README, or local scratch files into every Lambda.

---

# Design decisions

### Bedrock Converse instead of `invoke_model`

Converse is model-agnostic, so switching to Claude or Llama later is a change to
`BEDROCK_MODEL_ID` alone with no request-shape rewrite. Note that Converse takes
raw image **bytes** and base64-encodes internally, unlike `invoke_model`.

### Nova Pro over Claude

Claude has measurably better reasoning on nuanced fraud narratives but costs
roughly 10× more per token. Nova Pro is sufficient at this scope, and the model is
one environment variable.

### The fraud pattern library is bundled, not loaded from S3

The claim agent retrieves from `src/config/fraud_pattern_documents.json`, which
ships in the deployment package. That removes a runtime S3 read, and the
documents are versioned with the code that scores against them.

The real win is versioning: the patterns are the thing that decides whether a
customer gets accused of fraud, and having them travel with the code that prompts
on them means `git log` explains every change to a decision. A file in S3 can be
edited by anyone with write access, with no review and no history.

The cost is that editing a pattern means a redeploy. For a file this consequential
that's the right trade — and `sam deploy` on a text change takes about a minute.

### Vector retrieval instead of stuffing the whole library into the prompt

25 synthetic pattern documents still ship in the package
(`src/config/fraud_pattern_documents.json`). Agent 2 embeds the claim and
retrieves the top matches:

- **REAL AWS:** OpenSearch k-NN when `OPENSEARCH_ENDPOINT` is set, plus Titan embeddings.
- **DEGRADED (documented):** in-memory cosine similarity using the same Titan embeddings.
- **DEGRADED (documented):** lexical token overlap if embeddings fail. The result
  sets `tool_status.retrieval_mode = LEXICAL` and a limitation that this is not
  vector search.

The LLM is never asked to perform semantic search. Retrieved hits are passed into
the prompt as tool facts. OpenSearch Serverless is optional because of cost; the
in-memory index is the MVP default.

### An image URL is parsed, never fetched

`s3_image_url` is caller-supplied text naming a location, which in most systems is
the beginning of an SSRF bug. Resolving it to a `(bucket, key)` pair, rejecting any
bucket that isn't the configured one, and then reading through `s3:GetObject` with
the execution role means the URL never reaches an HTTP client. It also makes
presigned URLs work without being required, since the signature is discarded along
with the rest of the query string.

### Step Functions instead of chained Lambdas

Two agents need to run on one claim and something must combine them. Step
Functions gives retries with backoff for free, and a visual execution history —
which matters when debugging two AI agents whose outputs are non-deterministic.

### Timeouts sized for the retry path

`shared/bedrock_client.py` retries once with a stricter instruction when a model
returns unparseable JSON, so the worst case is two full model calls. The visual
agent's 180s timeout covers Hive's 20s plus two 50s Bedrock calls with headroom.
`BEDROCK_READ_TIMEOUT` is deliberately below every Lambda timeout so botocore
reports a timeout you can read in the logs, rather than the runtime being killed
mid-call.

### Agents never raise for terminal failures

Only transient failures raise, which lets the state machine retry on `States.ALL`
without retrying things that will never succeed. Terminal failures are recorded and
returned as `status: failed`, so the branch completes and the aggregator still
produces a degraded verdict.

### Untrusted text is fenced

Customer claim text reaches the model verbatim, making it a prompt-injection
vector. `bedrock_client.untrusted_block()` wraps it in delimiters, strips attempts
to close the fence early, and the system prompt states that the content is data and
never instructions.

## Security notes

- IAM is scoped to exact ARNs and single actions. The visual agent can read one
  prefix of one bucket; the claim agent can't touch S3 at all; the results
  function holds `dynamodb:Query` and nothing else. Log permissions come from the
  AWS-managed `AWSLambdaBasicExecutionRole`, which is account-scoped.
- A supplied `s3_image_url` is parsed rather than fetched, its bucket is compared
  against the configured bucket, and the resulting key is validated against a
  configured prefix with traversal blocked. There is no code path that turns
  caller-supplied text into an outbound HTTP request, which is what keeps a URL
  field from becoming an SSRF vector.
- `imaging.py` sets an explicit decompression-bomb ceiling, since it parses
  attacker-supplied image bytes.
- The claims table is `DeletionPolicy: Retain`, so `sam delete` leaves your fraud
  decisions intact. Delete it manually by the name in the stack outputs when you
  really mean it.
- The upload size cap now lives with the upload service, since they own
  presigning. Ask them to cap it — the visual agent downloads to `/tmp`, which is
  512 MB.

## Cost

| Component | Cost |
|---|---|
| Bedrock Nova Pro | ~$0.01–0.05 per agent call, vision at the high end |
| Hive Playground | Free, 100 requests/day |
| Step Functions | Standard workflows, ~$0.000025 per state transition |
| DynamoDB, Lambda, API Gateway | Effectively free at low volume |

A full two-agent analysis runs roughly **$0.02–0.10**. The API usage plan caps
requests per day, which is the real backstop against a runaway bill — lower
`ApiDailyQuota` for a tighter ceiling.
