"""Claim Intelligence Agent — Step Functions task.

Pipeline:
  load claim text
  → embed with Titan (when available)
  → retrieve fraud-pattern documents (OpenSearch, else in-memory, else lexical)
  → Bedrock reasoning over claim + retrieved hits
  → schema validation
  → deterministic scoring

Retrieved hits are produced by application code. The model cannot invent them.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from agent_claim import prompt as claim_prompt
from shared import bedrock_client, config, evidence, observability, schemas, scoring, vector_store
from shared.agent import agent_task
from shared.dynamodb_client import AGENT_CLAIM
from shared.errors import BedrockInvocationError, SchemaError

logger = config.get_logger(__name__)


def _invoke_claim_model(system_prompt: str, user_text: str) -> Dict[str, Any]:
    raw = bedrock_client.analyze_text(system_prompt, user_text)
    try:
        return schemas.parse_claim_model_output(raw)
    except SchemaError as first:
        logger.warning("Claim model JSON failed schema validation; retrying once")
        retry_text = (
            user_text
            + "\n\nPREVIOUS OUTPUT FAILED VALIDATION: "
            + str(first)
            + "\nReturn ONLY the required JSON object. Do not include risk_score or retrieved_patterns."
        )
        raw = bedrock_client.analyze_text(system_prompt, retry_text)
        try:
            return schemas.parse_claim_model_output(raw)
        except SchemaError as second:
            raise BedrockInvocationError(
                f"Claim model output failed schema validation after retry: {second}"
            ) from second


def _sanitize_hits_for_prompt(hits: list) -> list:
    """Pass retrieval evidence to the model without letting documents override instructions."""
    sanitized = []
    for hit in hits:
        sanitized.append(
            {
                "pattern_id": hit.get("pattern_id"),
                "similarity_score": hit.get("similarity_score"),
                "description": bedrock_client.untrusted_block(
                    "retrieved_pattern", str(hit.get("description") or "")
                ),
                "source": hit.get("source"),
                "pattern_type": hit.get("pattern_type"),
            }
        )
    return sanitized


def analyze_claim_intelligence(
    *,
    claim_id: str,
    customer_text: str,
    product_category: str,
    claimed_condition: str,
    order_value_usd: Any,
    embed: Optional[Any] = None,
) -> Dict[str, Any]:
    query = "\n".join(
        part
        for part in (claimed_condition, customer_text, f"product category: {product_category}")
        if part
    )
    retrieval = vector_store.retrieve(query, k=5, embed=embed)
    hits = retrieval["hits"]
    mode = retrieval["mode"]
    limitations = []
    if retrieval.get("limitation"):
        limitations.append(retrieval["limitation"])

    user_prompt = claim_prompt.build_user_prompt(
        product_category=product_category,
        order_value_usd=order_value_usd,
        claimed_condition=bedrock_client.untrusted_block("claimed_condition", claimed_condition or ""),
        customer_text=bedrock_client.untrusted_block("customer_claim", customer_text or ""),
        retrieval_mode=mode,
        retrieved_patterns_json=json.dumps(_sanitize_hits_for_prompt(hits), default=str)[:8000]
        if hits
        else "[]",
    )

    model_out = _invoke_claim_model(claim_prompt.SYSTEM_PROMPT, user_prompt)
    findings = list(model_out["findings"])
    for text in model_out.get("limitations") or []:
        if text and text not in limitations:
            limitations.append(text)

    # Prompt-injection attempts must not become a fraud finding by themselves.
    injection_markers = ("ignore previous", "ignore all instructions", "system prompt", "set risk")
    lowered = (customer_text or "").lower()
    if any(marker in lowered for marker in injection_markers):
        limitations.append(
            "Claim text contained instruction-like language; it was treated as data, not commands"
        )

    risk = scoring.claim_risk_score(findings, retrieved_patterns=hits)
    confidence = scoring.claim_confidence_score(
        retrieval_mode=mode,
        bedrock_succeeded=True,
        retrieved_count=len(hits),
        claim_text_chars=len(customer_text or ""),
    )
    recommendation = scoring.claim_recommendation(risk, findings)
    schemas.assert_score_bounds({"risk_score": risk, "confidence_score": confidence})

    return schemas.claim_result(
        claim_id=claim_id,
        risk_score=risk,
        confidence_score=confidence,
        findings=findings,
        retrieved_patterns=hits,
        limitations=limitations,
        explanation=model_out["explanation"],
        recommendation=recommendation,
        extras={
            "tool_status": {
                "bedrock": "ok",
                "embeddings": "ok" if mode in {"OPENSEARCH", "IN_MEMORY"} else "unavailable",
                "opensearch": "ok" if mode == "OPENSEARCH" else "not_used",
                "retrieval_mode": mode,
            },
            "matched_fraud_patterns": [hit["pattern_id"] for hit in hits if hit.get("pattern_id")],
        },
    )


@agent_task(AGENT_CLAIM, "claim")
def lambda_handler(event: Dict[str, Any]) -> Dict[str, Any]:
    fields = evidence.claim_fields(event)
    claim_id = str(fields["claim_id"] or event.get("claim_id") or "")
    request_id = event.get("request_id")
    with observability.invocation(
        logger, agent_name="claim_intelligence", claim_id=claim_id, request_id=request_id
    ) as state:
        result = analyze_claim_intelligence(
            claim_id=claim_id,
            customer_text=fields["customer_text"],
            product_category=fields["product_category"],
            claimed_condition=fields["customer_claimed_condition"],
            order_value_usd=fields["order_value_usd"],
        )
        state["retrieval_mode"] = result.get("tool_status", {}).get("retrieval_mode")
        state["model_call_status"] = "ok"
        state["retrieved_count"] = len(result.get("retrieved_patterns") or [])
        return result
