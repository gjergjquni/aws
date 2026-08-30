"""Visual Evidence Agent — Step Functions task.

Pipeline:
  resolve image references (S3 and/or local demo paths)
  → validate/decode
  → EXIF + perceptual hashes
  → Rekognition (explicit unavailable if it fails)
  → optional Hive enrichment
  → Bedrock multimodal reasoning over tool facts
  → schema validation
  → deterministic scoring

The model does not choose the risk score. Rekognition results are never faked.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence

from agent_visual import prompt as visual_prompt
from shared import (
    bedrock_client,
    config,
    evidence,
    hive_client,
    image_forensics,
    imaging,
    observability,
    rekognition_client,
    s3_utils,
    schemas,
    scoring,
)
from shared.agent import agent_task
from shared.dynamodb_client import AGENT_VISUAL
from shared.errors import BedrockInvocationError, EVIDENCE_MISSING, EvidenceError, SchemaError

logger = config.get_logger(__name__)


def check_with_hive(image_bytes: bytes, claim_id: str = "", content_type: str = "") -> Dict[str, Any]:
    """Back-compat wrapper. Prefer ``hive_client.moderate_visual``."""
    return hive_client.moderate_visual(
        image_bytes,
        claim_id=claim_id,
        content_type=content_type,
    )


def _collect_keys(event: Dict[str, Any]) -> List[Dict[str, str]]:
    """Normalized {bucket, key} objects. Does not re-parse HTTP URLs when evidence is present."""
    return evidence.from_event(event)


def _local_paths(event: Dict[str, Any]) -> List[str]:
    paths = event.get("local_image_paths") or []
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list):
        return []
    return [str(path) for path in paths if path][: config.max_evidence_images()]


def _invoke_visual_model(
    images: Sequence[bytes],
    system_prompt: str,
    user_text: str,
) -> Dict[str, Any]:
    raw = bedrock_client.analyze_images(list(images), system_prompt, user_text)
    try:
        return schemas.parse_visual_model_output(raw)
    except SchemaError as first:
        logger.warning("Visual model JSON failed schema validation; retrying once")
        retry_text = (
            user_text
            + "\n\nPREVIOUS OUTPUT FAILED VALIDATION: "
            + str(first)
            + "\nReturn ONLY the required JSON object. Do not include risk_score."
        )
        raw = bedrock_client.analyze_images(list(images), system_prompt, retry_text)
        try:
            return schemas.parse_visual_model_output(raw)
        except SchemaError as second:
            raise BedrockInvocationError(
                f"Visual model output failed schema validation after retry: {second}"
            ) from second


def analyze_visual_evidence(
    *,
    claim_id: str,
    product_category: str,
    claimed_condition: str,
    image_paths: Sequence[str],
    evidence_items: Optional[Sequence[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Core Agent 1 pipeline over local files already downloaded or supplied."""
    if not image_paths:
        raise EvidenceError(EVIDENCE_MISSING, "No evidence images were provided")

    limitations: List[str] = []
    code_findings: List[Dict[str, str]] = []
    rekognition_results: List[Dict[str, Any]] = []
    hive_result: Dict[str, Any] = hive_client.unavailable("not_run")
    hive_ok = False
    bounded_jpegs: List[bytes] = []
    technical: List[Dict[str, Any]] = []
    metadata_problems_all: List[str] = []
    exif_summaries: List[Dict[str, Optional[str]]] = []
    rekognition_ok = False
    metadata_present = False

    for index, path in enumerate(image_paths):
        with open(path, "rb") as handle:
            original = handle.read()
        observability.log_event(
            logger,
            event="IMAGE_DECODE_STARTED",
            claim_id=claim_id,
            image_index=index,
            byte_length=len(original),
            container=image_forensics.sniff_container(original),
        )
        summary = image_forensics.inspect_bytes(original, name=f"image[{index}]")
        exif_metadata = imaging.extract_exif(path)
        if any(key != "note" for key in exif_metadata):
            metadata_present = True
        problems = imaging.detect_metadata_problems(exif_metadata)
        metadata_problems_all.extend(problems)
        exif_summaries.append(imaging.summarize_exif(exif_metadata))
        jpeg_bytes, dimensions = imaging.to_bounded_jpeg(path)
        bounded_jpegs.append(jpeg_bytes)
        observability.log_event(
            logger,
            event="IMAGE_DECODE_SUCCESS",
            claim_id=claim_id,
            image_index=index,
            format=summary.get("format"),
            width=dimensions["width"],
            height=dimensions["height"],
        )
        summary["original_width"] = dimensions["width"]
        summary["original_height"] = dimensions["height"]
        summary["metadata_problems"] = problems
        summary["exif_redacted"] = imaging.redact_exif_for_prompt(exif_metadata)
        technical.append(summary)

        code_findings.extend(image_forensics.quality_findings(summary, index))
        code_findings.extend(image_forensics.metadata_findings(problems))

        rekognition = rekognition_client.analyze_image_bytes(jpeg_bytes, claim_id=claim_id)
        rekognition_results.append(rekognition)
        if rekognition.get("available"):
            rekognition_ok = True
            code_findings.extend(rekognition_client.findings_from_rekognition(rekognition, index))
            if rekognition.get("faces"):
                limitations.append(
                    f"Rekognition detected {rekognition['faces']} face(s) on image {index + 1}; "
                    "faces are not redacted before Bedrock in this MVP"
                )
        else:
            limitations.append(
                f"Rekognition unavailable for image {index + 1}: {rekognition.get('reason')}"
            )

        if index == 0:
            mime, ext = hive_client.mime_for_bytes(original)
            hive_result = hive_client.moderate_visual(
                original,
                claim_id=claim_id,
                content_type=mime,
                filename=f"evidence.{ext}",
            )
            hive_ok = bool(hive_result.get("success"))
            code_findings.extend(hive_result.get("findings") or [])
            if not hive_ok:
                code = hive_result.get("error_code") or "HIVE_NO_RESULT"
                limitations.append(f"Hive AI-generated/deepfake check unavailable: {code}")

    pairs = image_forensics.duplicate_pairs(technical)
    code_findings.extend(image_forensics.duplicate_findings(pairs))
    if len(image_paths) == 1:
        limitations.append("single_image_submitted: cross-image comparison was not possible")

    tool_facts = {
        "images": [
            {
                "index": i,
                "format": item["format"],
                "width": item["width"],
                "height": item["height"],
                "byte_length": item["byte_length"],
                "sha256_prefix": item["sha256"][:12],
                "metadata_problems": item["metadata_problems"],
                "exif": item["exif_redacted"],
                "rekognition": rekognition_results[i]
                if rekognition_results[i].get("available")
                else {"available": False, "reason": rekognition_results[i].get("reason")},
            }
            for i, item in enumerate(technical)
        ],
        "duplicate_pairs": pairs,
        "hive": {
            "provider": "hive",
            "available": hive_ok,
            "success": hive_ok,
            "task_id": hive_result.get("task_id"),
            "error_code": hive_result.get("error_code"),
            "scores": hive_result.get("scores") or {},
            "ai_generated": hive_result.get("ai_generated"),
            "deepfake": hive_result.get("deepfake"),
            "note": (
                "Hive AI-generated/deepfake scores are classifier outputs, not a fraud verdict."
            ),
        },
    }

    user_text = visual_prompt.build_user_prompt(
        product_category=product_category,
        claimed_condition=bedrock_client.untrusted_block("claimed_condition", claimed_condition),
        image_summaries=json.dumps(
            [
                {
                    "index": i,
                    "format": item["format"],
                    "dimensions": f"{item['width']}x{item['height']}",
                    "problems": item["metadata_problems"],
                }
                for i, item in enumerate(technical)
            ]
        ),
        tool_facts_json=json.dumps(tool_facts, default=str)[:12000],
        image_count=len(bounded_jpegs),
    )

    model_out = _invoke_visual_model(bounded_jpegs, visual_prompt.SYSTEM_PROMPT, user_text)
    findings = schemas.merge_unique_findings(code_findings, model_out["findings"])
    cross = list(model_out["cross_image_findings"])
    if pairs:
        cross = schemas.merge_unique_findings(cross, image_forensics.duplicate_findings(pairs))
    if len(image_paths) == 1:
        cross = []

    limitation_texts: List[str] = []
    for text in limitations + list(model_out.get("limitations") or []):
        if text and text not in limitation_texts:
            limitation_texts.append(text)

    unique_problems = []
    for flag in metadata_problems_all:
        if flag not in unique_problems:
            unique_problems.append(flag)

    risk = scoring.visual_risk_score(
        findings + cross,
        metadata_problems=unique_problems,
        hive_ai_score=hive_result.get("ai_generated"),
        duplicate_pairs=len(pairs),
    )
    confidence = scoring.visual_confidence_score(
        rekognition_available=rekognition_ok,
        hive_available=hive_ok,
        image_count=len(image_paths),
        metadata_present=metadata_present,
        bedrock_succeeded=True,
    )
    recommendation = scoring.visual_recommendation(risk, findings + cross)
    schemas.assert_score_bounds({"risk_score": risk, "confidence_score": confidence})

    first_exif = exif_summaries[0] if exif_summaries else {"camera": None, "timestamp": None, "software": None}
    return schemas.visual_result(
        claim_id=claim_id,
        risk_score=risk,
        confidence_score=confidence,
        findings=findings,
        cross_image_findings=cross,
        limitations=limitation_texts,
        explanation=model_out["explanation"],
        recommendation=recommendation,
        extras={
            "tool_status": {
                "rekognition": "ok" if rekognition_ok else "unavailable",
                "hive": "ok" if hive_ok else "unavailable",
                "bedrock": "ok",
                "s3": "local_or_downloaded",
            },
            "metadata_problems": unique_problems,
            "exif_data": first_exif,
            "hive_ai_score": hive_result.get("ai_generated"),
            "hive_deepfake_score": hive_result.get("deepfake"),
            "hive_available": hive_ok,
            "hive": {
                "provider": "hive",
                "success": hive_ok,
                "task_id": hive_result.get("task_id"),
                "error_code": hive_result.get("error_code"),
                "scores": hive_result.get("scores") or {},
                "raw_status": hive_result.get("raw_status"),
            },
            "image_count": len(image_paths),
            "visual_findings": [item["description"] for item in findings[:12]],
            "evidence_bucket": evidence_items[0]["bucket"] if evidence_items else None,
            "evidence_key": evidence_items[0]["key"] if evidence_items else None,
            "evidence_keys": [item["key"] for item in evidence_items] if evidence_items else [],
            "evidence_sha256": technical[0]["sha256"] if technical else None,
        },
    )


@agent_task(AGENT_VISUAL, "visual")
def lambda_handler(event: Dict[str, Any]) -> Dict[str, Any]:
    fields = evidence.claim_fields(event)
    claim_id = fields["claim_id"]
    product_category = fields["product_category"]
    claimed_condition = fields["customer_claimed_condition"]
    request_id = event.get("request_id")

    local_paths = _local_paths(event)
    with observability.invocation(
        logger, agent_name="visual_evidence", claim_id=str(claim_id), request_id=request_id
    ) as state:
        if local_paths:
            state["image_source"] = "local"
            observability.log_event(
                logger, event="IMAGE_ANALYSIS_STARTED", claim_id=str(claim_id), image_source="local"
            )
            result = analyze_visual_evidence(
                claim_id=str(claim_id),
                product_category=product_category,
                claimed_condition=claimed_condition,
                image_paths=local_paths,
            )
            observability.log_event(
                logger, event="IMAGE_ANALYSIS_SUCCESS", claim_id=str(claim_id), image_source="local"
            )
            state["rekognition"] = result.get("tool_status", {}).get("rekognition")
            state["model_call_status"] = "ok"
            return result

        items = _collect_keys(event)
        if not items:
            raise EvidenceError(EVIDENCE_MISSING, "Missing required field: s3_image_url")
        state["image_source"] = "s3"
        state["image_count"] = len(items)
        state["evidence_key"] = items[0]["key"]

        with tempfile.TemporaryDirectory() as workspace:
            paths = []
            for index, item in enumerate(items):
                s3_utils.head_object(item["key"])
                destination = os.path.join(workspace, f"evidence-{index}")
                s3_utils.download_object(item["key"], destination, bucket=item["bucket"])
                paths.append(destination)
            observability.log_event(
                logger, event="IMAGE_ANALYSIS_STARTED", claim_id=str(claim_id), image_count=len(paths)
            )
            result = analyze_visual_evidence(
                claim_id=str(claim_id),
                product_category=product_category,
                claimed_condition=claimed_condition,
                image_paths=paths,
                evidence_items=items,
            )
        observability.log_event(
            logger, event="IMAGE_ANALYSIS_SUCCESS", claim_id=str(claim_id), image_count=len(items)
        )
        state["rekognition"] = result.get("tool_status", {}).get("rekognition")
        state["model_call_status"] = "ok"
        return result
