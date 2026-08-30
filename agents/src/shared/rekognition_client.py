"""Amazon Rekognition adapter.

Never fabricates detections. If the client is unavailable, credentials are
missing, or the API errors, callers receive an explicit unavailable result.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError

from . import aws, config, observability
from .errors import RetryableAgentError

logger = config.get_logger(__name__)

_RETRYABLE = {
    "ThrottlingException",
    "ProvisionedThroughputExceededException",
    "ServiceUnavailableException",
    "InternalServerError",
}


def _client() -> Any:
    return aws.client("rekognition", read_timeout=20, max_attempts=1)


def unavailable(reason: str) -> Dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "labels": [],
        "text": [],
        "moderation": [],
        "faces": 0,
    }


def analyze_image_bytes(image_bytes: bytes, claim_id: str = "") -> Dict[str, Any]:
    """Run label, text, moderation, and face detection on one image.

    Rekognition is called with bytes (not S3 object references) so this works
    for both Lambda downloads and local demo files.
    """
    image = {"Bytes": image_bytes}
    min_conf = config.rekognition_min_confidence()
    max_labels = config.rekognition_max_labels()

    try:
        labels_resp = _client().detect_labels(
            Image=image, MaxLabels=max_labels, MinConfidence=min_conf
        )
        text_resp = _client().detect_text(Image=image)
        moderation_resp = _client().detect_moderation_labels(
            Image=image, MinConfidence=min_conf
        )
        faces_resp = _client().detect_faces(Image=image, Attributes=["DEFAULT"])
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        message = exc.response.get("Error", {}).get("Message", str(exc))
        observability.aws_failure(
            logger, service="rekognition", operation="detect", error=f"{code}: {message}", claim_id=claim_id
        )
        if code in _RETRYABLE:
            raise RetryableAgentError(f"Rekognition {code}") from exc
        return unavailable(f"{code}: {message}")
    except BotoCoreError as exc:
        observability.aws_failure(
            logger, service="rekognition", operation="detect", error=str(exc), claim_id=claim_id
        )
        raise RetryableAgentError(f"Rekognition transport failure: {exc}") from exc

    labels = [
        {
            "name": entry.get("Name", ""),
            "confidence": round(float(entry.get("Confidence", 0.0)), 2),
            "parents": [parent.get("Name", "") for parent in entry.get("Parents") or [] if parent.get("Name")],
        }
        for entry in labels_resp.get("Labels") or []
        if isinstance(entry, dict) and entry.get("Name")
    ]
    text_lines: List[str] = []
    for detection in text_resp.get("TextDetections") or []:
        if not isinstance(detection, dict):
            continue
        if detection.get("Type") == "LINE" and detection.get("DetectedText"):
            text_lines.append(str(detection["DetectedText"])[:200])
    moderation = [
        {
            "name": entry.get("Name", ""),
            "confidence": round(float(entry.get("Confidence", 0.0)), 2),
        }
        for entry in moderation_resp.get("ModerationLabels") or []
        if isinstance(entry, dict) and entry.get("Name")
    ]
    faces = len(faces_resp.get("FaceDetails") or [])

    observability.log_event(
        logger,
        event="rekognition_ok",
        claim_id=claim_id or None,
        labels=len(labels),
        text_lines=len(text_lines),
        moderation=len(moderation),
        faces=faces,
    )
    return {
        "available": True,
        "reason": None,
        "labels": labels,
        "text": text_lines[:30],
        "moderation": moderation,
        "faces": faces,
    }


def findings_from_rekognition(result: Dict[str, Any], image_index: int) -> List[Dict[str, str]]:
    """Convert real Rekognition output into schema findings. Never invents labels."""
    if not result.get("available"):
        return []
    findings: List[Dict[str, str]] = []
    names = [item["name"] for item in result.get("labels") or [] if item.get("name")]
    if names:
        findings.append(
            {
                "category": "REKOGNITION_LABEL",
                "severity": "LOW",
                "description": f"Rekognition labels on image {image_index + 1}: {', '.join(names[:12])}",
                "evidence": f"detect_labels returned {len(names)} labels",
                "source": "rekognition",
            }
        )
    text_lines = result.get("text") or []
    if text_lines:
        preview = "; ".join(text_lines[:5])
        findings.append(
            {
                "category": "REKOGNITION_TEXT",
                "severity": "LOW",
                "description": f"Rekognition OCR on image {image_index + 1} detected text",
                "evidence": preview[:400],
                "source": "rekognition",
            }
        )
    for label in result.get("moderation") or []:
        findings.append(
            {
                "category": "OTHER",
                "severity": "MEDIUM",
                "description": f"Rekognition moderation label on image {image_index + 1}: {label.get('name')}",
                "evidence": f"confidence={label.get('confidence')}",
                "source": "rekognition",
            }
        )
    return findings
