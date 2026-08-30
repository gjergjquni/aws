"""Canonical evidence-upload helpers.

The object key is generated once and reused for the presigned PUT, the
stored claim record, and the s3_url sent to Aegis Agent 1. No fixture
keys (uploads/test.jpg) are produced here.
"""

from __future__ import annotations

import json
import logging
import re
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
}

HEIC_TYPES = {
    "image/heic",
    "image/heif",
    "image/heic-sequence",
    "image/heif-sequence",
}

EXT_TO_CONTENT_TYPE = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}

REJECTED_EXTENSIONS = {"heic", "heif", "heics", "avif", "webp", "gif", "bmp", "tif", "tiff"}

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

MAX_IMAGE_BYTES = 10 * 1024 * 1024
S3_URI_RE = re.compile(r"^s3://([^/]+)/(.+)$")
SAFE_CLAIM_ID_RE = re.compile(r"[^A-Za-z0-9._-]")


class EvidenceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def as_body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def log_event(event: str, **fields) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, default=str))


def sanitize_claim_id(claim_id: str | None) -> str:
    raw = (claim_id or "").strip() or str(uuid.uuid4())
    cleaned = SAFE_CLAIM_ID_RE.sub("", raw)
    return cleaned or str(uuid.uuid4())


def _extension_from_filename(filename: str | None) -> str | None:
    if not filename or "." not in filename:
        return None
    return filename.rsplit(".", 1)[-1].lower().lstrip()


def resolve_content_type(content_type: str | None, filename: str | None = None) -> str:
    mime = (content_type or "").split(";")[0].strip().lower()
    ext = _extension_from_filename(filename)

    if mime in HEIC_TYPES or ext in {"heic", "heif", "heics"}:
        raise EvidenceError(
            "EVIDENCE_UNSUPPORTED_FORMAT",
            "Only JPEG and PNG images are supported.",
        )

    if ext in REJECTED_EXTENSIONS:
        raise EvidenceError(
            "EVIDENCE_UNSUPPORTED_FORMAT",
            "Only JPEG and PNG images are supported.",
        )

    mime_ok = mime in ALLOWED_CONTENT_TYPES
    ext_ok = ext in EXT_TO_CONTENT_TYPE

    if mime and mime not in ALLOWED_CONTENT_TYPES and mime not in {"application/octet-stream", ""}:
        raise EvidenceError(
            "EVIDENCE_UNSUPPORTED_FORMAT",
            "Only JPEG and PNG images are supported.",
        )

    if mime_ok and ext_ok:
        mapped = EXT_TO_CONTENT_TYPE[ext]
        if mapped != mime:
            raise EvidenceError(
                "EVIDENCE_UNSUPPORTED_FORMAT",
                "Only JPEG and PNG images are supported.",
            )
        return mime

    if mime_ok:
        return mime
    if ext_ok:
        return EXT_TO_CONTENT_TYPE[ext]

    raise EvidenceError(
        "EVIDENCE_UNSUPPORTED_FORMAT",
        "Only JPEG and PNG images are supported.",
    )


def validate_declared_size(content_length: int | None) -> None:
    if content_length is None:
        return
    if content_length <= 0:
        raise EvidenceError("EVIDENCE_EMPTY", "Image file is empty.")
    if content_length > MAX_IMAGE_BYTES:
        raise EvidenceError(
            "EVIDENCE_TOO_LARGE",
            f"Image exceeds the maximum size of {MAX_IMAGE_BYTES} bytes.",
        )


def generate_object_key(claim_id: str, content_type: str, prefix: str = "uploads") -> str:
    clean_prefix = (prefix or "uploads").strip("/")
    if clean_prefix != "uploads":
        # Agent 1 only reads uploads/. Never emit evidence/ for Aegis.
        clean_prefix = "uploads"
    ext = ALLOWED_CONTENT_TYPES[content_type]
    return f"{clean_prefix}/{sanitize_claim_id(claim_id)}/{uuid.uuid4()}.{ext}"


def canonical_s3_url(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def parse_s3_url(s3_url: str) -> tuple[str, str]:
    match = S3_URI_RE.match(s3_url.strip())
    if not match:
        raise EvidenceError(
            "EVIDENCE_INVALID_URL",
            "Send an S3 URL or bare key — not CloudFront, not https://.",
        )
    return match.group(1), match.group(2)


def _reject_http_url(value: str) -> None:
    lowered = value.strip().lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        raise EvidenceError(
            "EVIDENCE_INVALID_URL",
            "Send an S3 URL or bare key — not CloudFront, not https://.",
        )


def resolve_evidence_location(body: dict, upload_bucket: str) -> tuple[str, str, str]:
    """Return (bucket, key, s3_url) from the claim body. No fixture fallback."""
    raw_url = (body.get("s3_url") or "").strip()
    raw_key = (body.get("s3_key") or body.get("s3_image_url") or "").strip()

    if not raw_url and not raw_key:
        raise EvidenceError("EVIDENCE_MISSING", "An evidence image is required.")

    if raw_url:
        _reject_http_url(raw_url)
        if raw_url.startswith("s3://"):
            bucket, key = parse_s3_url(raw_url)
        else:
            bucket, key = upload_bucket, raw_url.lstrip("/")
    else:
        _reject_http_url(raw_key)
        if raw_key.startswith("s3://"):
            bucket, key = parse_s3_url(raw_key)
        else:
            bucket, key = upload_bucket, raw_key.lstrip("/")

    if bucket != upload_bucket:
        raise EvidenceError(
            "EVIDENCE_INVALID_URL",
            "s3_url bucket does not match the configured evidence bucket.",
        )

    if not key.startswith("uploads/"):
        raise EvidenceError(
            "EVIDENCE_INVALID_URL",
            "Object key must start with uploads/.",
        )

    return bucket, key, canonical_s3_url(bucket, key)


def detect_image_content_type(header: bytes) -> str | None:
    if header.startswith(JPEG_MAGIC):
        return "image/jpeg"
    if header.startswith(PNG_MAGIC):
        return "image/png"
    return None


def create_presigned_upload(s3_client, body: dict, bucket: str, prefix: str) -> dict:
    claim_id = sanitize_claim_id(body.get("claim_id"))
    content_type = resolve_content_type(body.get("content_type"), body.get("filename"))
    raw_length = body.get("content_length")
    declared_length = int(raw_length) if raw_length is not None and str(raw_length) != "" else None
    validate_declared_size(declared_length)

    key = generate_object_key(claim_id, content_type, prefix)
    s3_url = canonical_s3_url(bucket, key)

    log_event(
        "UPLOAD_STARTED",
        claim_id=claim_id,
        bucket=bucket,
        key=key,
        content_type=content_type,
        content_length=declared_length,
    )

    upload_url = s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=300,
    )

    return {
        "claim_id": claim_id,
        "upload_url": upload_url,
        "s3_key": key,
        "bucket": bucket,
        "s3_url": s3_url,
        "content_type": content_type,
    }


def verify_uploaded_object(s3_client, bucket: str, key: str, expected_content_type: str | None = None) -> dict:
    try:
        head = s3_client.head_object(Bucket=bucket, Key=key)
    except Exception as exc:
        code = ""
        response = getattr(exc, "response", None)
        if isinstance(response, dict):
            code = response.get("Error", {}).get("Code", "")
        if code in {"404", "NoSuchKey", "NotFound"}:
            raise EvidenceError("EVIDENCE_NOT_FOUND", "Uploaded evidence object was not found in S3.", 404) from exc
        if code in {"403", "AccessDenied"}:
            raise EvidenceError("EVIDENCE_ACCESS_DENIED", "Cannot read uploaded evidence from S3.", 403) from exc
        raise EvidenceError("EVIDENCE_NOT_FOUND", "Uploaded evidence object was not found in S3.", 404) from exc

    length = int(head.get("ContentLength") or 0)
    stored_type = (head.get("ContentType") or "").split(";")[0].strip().lower()
    validate_declared_size(length)

    try:
        obj = s3_client.get_object(Bucket=bucket, Key=key, Range="bytes=0-15")
        header = obj["Body"].read()
    except Exception:
        header = b""

    detected = detect_image_content_type(header) if header else None
    resolved_type = detected or stored_type
    if resolved_type not in ALLOWED_CONTENT_TYPES:
        raise EvidenceError(
            "EVIDENCE_UNSUPPORTED_FORMAT",
            "Only JPEG and PNG images are supported.",
        )
    if expected_content_type and detected and detected != expected_content_type:
        raise EvidenceError(
            "EVIDENCE_UNSUPPORTED_FORMAT",
            "Only JPEG and PNG images are supported.",
        )

    log_event(
        "UPLOAD_VERIFIED",
        bucket=bucket,
        key=key,
        content_type=resolved_type,
        content_length=length,
    )

    return {
        "bucket": bucket,
        "key": key,
        "content_type": resolved_type,
        "content_length": length,
    }
