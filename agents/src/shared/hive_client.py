"""Hive V3 AI-generated and deepfake detection for Agent 1.

Documented contract (Playground / V3):

    POST https://api.thehive.ai/api/v3/hive/ai-generated-and-deepfake-content-detection
    Authorization: Bearer <SECRET_KEY>
    multipart/form-data: media = <downloaded image bytes>

Never send a private S3 URL. Hive is one signal, not a fraud verdict.
"""

from __future__ import annotations

import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config, observability, secrets
from .errors import (
    HIVE_AUTH_FAILED,
    HIVE_BAD_REQUEST,
    HIVE_CONFIGURATION_ERROR,
    HIVE_INVALID_RESPONSE,
    HIVE_NO_RESULT,
    HIVE_RATE_LIMITED,
    HIVE_SERVER_ERROR,
    HIVE_TIMEOUT,
    HIVE_UNSUPPORTED_MEDIA,
)

logger = config.get_logger(__name__)

_MIME_BY_CONTAINER = {
    "jpeg": ("image/jpeg", "jpg"),
    "png": ("image/png", "png"),
    "webp": ("image/webp", "webp"),
    "gif": ("image/gif", "gif"),
}

# Hive V3 AI-generated / deepfake heads. Threshold 0.9 per Hive docs.
_MANIPULATION_CLASSES = frozenset({"deepfake", "yes_deepfake"})
_POLICY_CLASSES = frozenset()
_AI_CLASSES = frozenset(
    {
        "ai_generated",
        "yes_ai_generated",
        "ai_generated_media",
    }
)
_SKIP_CLASSES = frozenset(
    {
        "not_ai_generated",
        "not_ai_generated_audio",
        "none",
        "inconclusive",
        "inconclusive_video",
        "no_deepfake",
    }
)


def mime_for_bytes(image_bytes: bytes, content_type: str = "") -> Tuple[str, str]:
    """Return (mime, filename extension) from Content-Type or magic bytes."""
    lowered = (content_type or "").split(";")[0].strip().lower()
    if lowered in {"image/jpeg", "image/jpg", "image/pjpeg"}:
        return "image/jpeg", "jpg"
    if lowered in {"image/png", "image/x-png"}:
        return "image/png", "png"
    if lowered == "image/webp":
        return "image/webp", "webp"
    if lowered == "image/gif":
        return "image/gif", "gif"

    from . import image_forensics

    kind = image_forensics.sniff_container(image_bytes)
    mime, ext = _MIME_BY_CONTAINER.get(kind, ("application/octet-stream", "bin"))
    return mime, ext


def unavailable(reason: str, error_code: Optional[str] = None) -> Dict[str, Any]:
    return {
        "provider": "hive",
        "success": False,
        "task_id": None,
        "findings": [],
        "scores": {},
        "raw_status": "unavailable",
        "error_code": error_code,
        "http_status": None,
        "reason": reason,
        "ai_generated": None,
        "deepfake": None,
    }


def _classify_http(status: int, message: str) -> str:
    combined = (message or "").lower()
    if status in {401, 403}:
        return HIVE_AUTH_FAILED
    if status == 429:
        return HIVE_RATE_LIMITED
    if status == 400:
        if any(token in combined for token in ("media", "format", "mimetype", "unsupported", "file type")):
            return HIVE_UNSUPPORTED_MEDIA
        return HIVE_BAD_REQUEST
    if status >= 500:
        return HIVE_SERVER_ERROR
    return HIVE_BAD_REQUEST


def _retryable(error_code: str) -> bool:
    return error_code in {HIVE_RATE_LIMITED, HIVE_SERVER_ERROR, HIVE_TIMEOUT}


def _extract_classes(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Hive V3: output[0].classes. Also accepts the older V2 status wrapper."""
    status = payload.get("status")
    outputs: List[Any] = []
    if isinstance(status, list) and status:
        first = status[0] if isinstance(status[0], dict) else {}
        response = first.get("response") if isinstance(first.get("response"), dict) else {}
        output = response.get("output")
        if isinstance(output, list):
            outputs.extend(output)
        inner_status = first.get("status")
        if isinstance(inner_status, dict) and str(inner_status.get("message") or "").upper() not in {"", "SUCCESS"}:
            pass
    if isinstance(payload.get("output"), list):
        outputs.extend(payload["output"])

    classes: List[Dict[str, Any]] = []
    for frame in outputs:
        if not isinstance(frame, dict):
            continue
        for entry in frame.get("classes") or []:
            if not isinstance(entry, dict):
                continue
            label = entry.get("class")
            score = entry.get("score", entry.get("value"))
            if isinstance(label, str) and isinstance(score, (int, float)):
                classes.append({"class": label, "score": float(score)})
    return classes


def _task_id(payload: Dict[str, Any]) -> Optional[str]:
    value = payload.get("task_id") or payload.get("id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    ids = payload.get("task_ids")
    if isinstance(ids, list) and ids and isinstance(ids[0], str):
        return ids[0]
    status = payload.get("status")
    if isinstance(status, list) and status and isinstance(status[0], dict):
        response = status[0].get("response") if isinstance(status[0].get("response"), dict) else {}
        model_input = response.get("input") if isinstance(response.get("input"), dict) else {}
        nested = model_input.get("id")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _error_message(payload: Any, fallback: str) -> str:
    if not isinstance(payload, dict):
        return fallback
    for key in ("message", "error", "error_code"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip() and key != "error":
            return value.strip()[:300]
        if isinstance(value, dict) and isinstance(value.get("message"), str):
            return value["message"].strip()[:300]
    return fallback[:300]


def findings_from_scores(
    scores: Dict[str, float],
    *,
    image_index: int = 0,
    threshold: Optional[float] = None,
) -> List[Dict[str, str]]:
    cut = config.hive_moderation_threshold() if threshold is None else threshold
    findings: List[Dict[str, str]] = []
    for label, score in scores.items():
        if score < cut:
            continue
        if label in _SKIP_CLASSES or label.startswith("not_"):
            continue
        if label in _MANIPULATION_CLASSES:
            category, severity = "MANIPULATION", "HIGH" if score >= 0.95 else "MEDIUM"
        elif label in _AI_CLASSES:
            category, severity = "AI_SYNTHETIC", "HIGH" if score >= 0.9 else "MEDIUM"
        elif label in _POLICY_CLASSES:
            category, severity = "OTHER", "MEDIUM"
        else:
            continue
        findings.append(
            {
                "category": category,
                "severity": severity,
                "description": (
                    f"Hive AI-generated/deepfake model scored image {image_index + 1} as "
                    f"{score:.2f} for {label} (classifier output, not a fraud verdict)"
                ),
                "evidence": f"hive_{label}={score:.4f}",
                "source": "hive",
            }
        )
    return findings


def _public_scores(scores: Dict[str, float]) -> Dict[str, float]:
    """Keep elevated scores only — not the full Hive class list."""
    return {label: round(score, 4) for label, score in scores.items() if score >= 0.5}


def moderate_visual(
    image_bytes: bytes,
    *,
    claim_id: str = "",
    content_type: str = "",
    filename: str = "",
) -> Dict[str, Any]:
    """Send downloaded image bytes to Hive V3. Never sends an S3 URL."""
    if not image_bytes:
        result = unavailable("empty image", HIVE_UNSUPPORTED_MEDIA)
        observability.log_event(
            logger,
            event="HIVE_REQUEST_FAILED",
            claim_id=claim_id or None,
            error_code=HIVE_UNSUPPORTED_MEDIA,
            image_size=0,
        )
        return result

    credentials = secrets.get_hive_credentials()
    if not credentials["ok"]:
        code = credentials.get("error_code") or HIVE_CONFIGURATION_ERROR
        observability.log_event(
            logger,
            event="HIVE_REQUEST_FAILED",
            claim_id=claim_id or None,
            error_code=code,
            hive_secret_fields=credentials.get("fields") or None,
        )
        return unavailable(credentials.get("reason") or "Hive is not configured", code)

    api_key = credentials["api_key"]
    mime, ext = mime_for_bytes(image_bytes, content_type)
    name = filename or f"evidence.{ext}"
    url = config.hive_sync_url()
    timeout = config.hive_timeout_seconds()
    attempts = 1 + config.hive_max_retries()

    observability.log_event(
        logger,
        event="HIVE_REQUEST_STARTED",
        claim_id=claim_id or None,
        content_type=mime,
        image_size=len(image_bytes),
        hive_endpoint=url,
    )

    last_error = HIVE_SERVER_ERROR
    last_status: Optional[int] = None
    last_message = "Hive request failed"
    payload: Optional[Dict[str, Any]] = None

    for attempt in range(attempts):
        try:
            reply = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
                files={
                    "media": (name, BytesIO(image_bytes), mime),
                },
                timeout=timeout,
            )
        except requests.Timeout as exc:
            last_error = HIVE_TIMEOUT
            last_message = "Hive request timed out"
            observability.log_event(
                logger,
                event="HIVE_REQUEST_FAILED",
                claim_id=claim_id or None,
                error_code=HIVE_TIMEOUT,
                attempt=attempt + 1,
                content_type=mime,
                image_size=len(image_bytes),
            )
            if attempt + 1 < attempts and _retryable(HIVE_TIMEOUT):
                time.sleep(0.4 * (2**attempt))
                continue
            return unavailable(last_message, HIVE_TIMEOUT)
        except requests.RequestException as exc:
            last_error = HIVE_SERVER_ERROR
            last_message = f"Hive transport error: {type(exc).__name__}"
            observability.log_event(
                logger,
                event="HIVE_REQUEST_FAILED",
                claim_id=claim_id or None,
                error_code=HIVE_SERVER_ERROR,
                attempt=attempt + 1,
                content_type=mime,
                image_size=len(image_bytes),
            )
            if attempt + 1 < attempts:
                time.sleep(0.4 * (2**attempt))
                continue
            return unavailable(last_message, HIVE_SERVER_ERROR)

        last_status = reply.status_code
        body: Any = {}
        try:
            body = reply.json() if reply.content else {}
        except ValueError:
            body = {}

        if reply.status_code in {200, 201}:
            payload = body if isinstance(body, dict) else None
            break

        last_message = _error_message(body, f"Hive HTTP {reply.status_code}")
        last_error = _classify_http(reply.status_code, last_message)
        observability.log_event(
            logger,
            event="HIVE_REQUEST_FAILED",
            claim_id=claim_id or None,
            error_code=last_error,
            http_status=reply.status_code,
            hive_message=last_message,
            attempt=attempt + 1,
            content_type=mime,
            image_size=len(image_bytes),
        )
        if attempt + 1 < attempts and _retryable(last_error):
            time.sleep(0.4 * (2**attempt))
            continue
        return unavailable(last_message, last_error)

    if not isinstance(payload, dict):
        observability.log_event(
            logger,
            event="HIVE_REQUEST_FAILED",
            claim_id=claim_id or None,
            error_code=HIVE_INVALID_RESPONSE,
            http_status=last_status,
            content_type=mime,
            image_size=len(image_bytes),
        )
        return unavailable("Hive returned a non-JSON body", HIVE_INVALID_RESPONSE)

    classes = _extract_classes(payload)
    task_id = _task_id(payload)
    if payload.get("error") and not classes:
        message = _error_message(payload, "Hive reported an error")
        observability.log_event(
            logger,
            event="HIVE_REQUEST_FAILED",
            claim_id=claim_id or None,
            error_code=HIVE_INVALID_RESPONSE,
            http_status=last_status,
            hive_message=message,
            content_type=mime,
            image_size=len(image_bytes),
        )
        return unavailable(message, HIVE_INVALID_RESPONSE)

    if not classes:
        observability.log_event(
            logger,
            event="HIVE_REQUEST_FAILED",
            claim_id=claim_id or None,
            error_code=HIVE_NO_RESULT,
            http_status=last_status,
            task_id=task_id,
            content_type=mime,
            image_size=len(image_bytes),
        )
        return {
            **unavailable("Hive returned no visual class scores", HIVE_NO_RESULT),
            "task_id": task_id,
            "http_status": last_status,
            "raw_status": "no_result",
        }

    scores = {item["class"]: item["score"] for item in classes}
    findings = findings_from_scores(scores)
    ai_score = next((scores[name] for name in _AI_CLASSES if name in scores), None)
    deepfake = scores.get("deepfake")
    if deepfake is None:
        deepfake = scores.get("yes_deepfake")

    observability.log_event(
        logger,
        event="HIVE_REQUEST_SUCCESS",
        claim_id=claim_id or None,
        http_status=last_status,
        task_id=task_id,
        content_type=mime,
        image_size=len(image_bytes),
        finding_count=len(findings),
    )
    return {
        "provider": "hive",
        "success": True,
        "task_id": task_id,
        "findings": findings,
        "scores": _public_scores(scores),
        "raw_status": "success",
        "error_code": None,
        "http_status": last_status,
        "reason": None,
        "ai_generated": ai_score,
        "deepfake": deepfake,
        "content_type": mime,
        "image_size": len(image_bytes),
    }
