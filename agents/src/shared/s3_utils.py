"""Read-only S3 access to evidence photos.

Canonical internal representation after intake:

    {"bucket": <EVIDENCE_BUCKET>, "key": "<prefix>...<object>"}

The application backend may send ``s3://``, virtual-hosted or path-style HTTPS,
a presigned GET URL, or a bare key. Those are parsed here once. Query strings
(including presigned signatures) are discarded. Download always uses
``s3:GetObject`` with the Lambda execution role — never HTTP GET of the URL.

The bucket in a URL is compared against ``EVIDENCE_BUCKET`` and refused if it
differs. Agent 1 must not re-parse the original URL; it receives the normalized
``evidence`` object from Step Functions.
"""

from __future__ import annotations

import posixpath
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote, urlsplit

from botocore.exceptions import ClientError

from . import aws, config, observability
from .errors import (
    EVIDENCE_ACCESS_DENIED,
    EVIDENCE_BUCKET_MISMATCH,
    EVIDENCE_DOWNLOAD_FAILED,
    EVIDENCE_EMPTY,
    EVIDENCE_INVALID,
    EVIDENCE_INVALID_KEY,
    EVIDENCE_INVALID_URL,
    EVIDENCE_KMS_ACCESS_DENIED,
    EVIDENCE_NOT_FOUND,
    EvidenceError,
)

logger = config.get_logger(__name__)

MAX_KEY_LENGTH = 1024
MAX_REFERENCE_LENGTH = 2048

# Known local smoke-test objects. Production must never treat these as a user photo.
_RESERVED_FIXTURE_KEYS = frozenset(
    {
        "test.jpg",
        "test.jpeg",
        "test.png",
    }
)

# Path-style endpoints: s3.amazonaws.com, s3.us-east-1.amazonaws.com,
# s3-us-west-2.amazonaws.com. The bucket is the first path segment.
_PATH_STYLE_HOST = re.compile(r"^s3([.-][a-z0-9-]+)?\.amazonaws\.com$")

# Virtual-hosted style: bucket.s3.amazonaws.com, bucket.s3.us-east-1.amazonaws.com,
# bucket.s3-accelerate.amazonaws.com, bucket.s3.dualstack.us-east-1.amazonaws.com.
_VIRTUAL_HOST = re.compile(r"^(?P<bucket>.+?)\.s3([.-][a-z0-9-]+)*\.amazonaws\.com$")


def _client() -> Any:
    return aws.client("s3", read_timeout=30)


def redact_reference(raw: str) -> str:
    """Drop query/fragment so logs never contain a presigned signature."""
    if not isinstance(raw, str) or not raw:
        return ""
    if "?" in raw:
        return raw.split("?", 1)[0]
    if "#" in raw:
        return raw.split("#", 1)[0]
    return raw


def _split_http_reference(raw: str, field: str) -> Tuple[Optional[str], str]:
    parts = urlsplit(raw)
    host = parts.netloc.split("@")[-1].split(":")[0].lower()
    path = unquote(parts.path).lstrip("/")

    if _PATH_STYLE_HOST.match(host):
        bucket, _, key = path.partition("/")
        return bucket, key

    virtual = _VIRTUAL_HOST.match(host)
    if virtual:
        return virtual.group("bucket"), path

    raise EvidenceError(
        EVIDENCE_INVALID_URL,
        (
            f"{field} must be an S3 URL (s3:// or https://<bucket>.s3.<region>.amazonaws.com/...), "
            "a presigned S3 GET URL, or a bare object key under the configured prefix. "
            "CloudFront, custom domains, and application image routes are not accepted — "
            "Agent 1 downloads with IAM, not HTTP."
        ),
    )


def _split_reference(raw: str, field: str) -> Tuple[Optional[str], str]:
    lowered = raw.lower()
    if lowered.startswith("s3://"):
        bucket, _, key = raw[5:].partition("/")
        return bucket, key
    if lowered.startswith(("http://", "https://")):
        return _split_http_reference(raw, field)
    return None, raw


def normalize_evidence_reference(value: Any, field: str = "s3_image_url") -> Dict[str, str]:
    """Reduce a caller-supplied image reference to ``{bucket, key}``.

    Does not fetch the URL. The returned bucket is always the configured
    evidence bucket after a match check.
    """
    raw = value.strip() if isinstance(value, str) else ""
    if not raw:
        raise EvidenceError(
            EVIDENCE_INVALID,
            "A valid S3 evidence object is required.",
        )
    if len(raw) > MAX_REFERENCE_LENGTH:
        raise EvidenceError(EVIDENCE_INVALID_URL, f"{field} is too long")

    named_bucket, key = _split_reference(raw, field)
    expected = config.bucket_name()
    if named_bucket and named_bucket != expected:
        logger.warning(
            "Rejected %s pointing at bucket %r, expected %r",
            field,
            named_bucket,
            expected,
        )
        observability.log_event(
            logger,
            event="EVIDENCE_BUCKET_MISMATCH",
            field=field,
            supplied_bucket=named_bucket,
            expected_bucket=expected,
            reference=redact_reference(raw),
        )
        raise EvidenceError(
            EVIDENCE_BUCKET_MISMATCH,
            "The supplied evidence belongs to a different S3 bucket.",
        )

    validated = validate_evidence_key(key, field=field)
    normalized = {"bucket": expected, "key": validated}
    observability.log_event(
        logger,
        event="EVIDENCE_NORMALIZED",
        field=field,
        bucket=expected,
        key=validated,
        reference=redact_reference(raw),
    )
    return normalized


def resolve_evidence_reference(value: Any, field: str = "s3_image_url") -> str:
    """Back-compat: return only the object key. Prefer ``normalize_evidence_reference``."""
    return normalize_evidence_reference(value, field=field)["key"]


def _reject_reserved_fixture(candidate: str, field: str) -> None:
    """Refuse uploads/test.jpg in production so a fixture cannot replace a user photo."""
    if config.allow_evidence_fixtures():
        return
    prefix = config.evidence_key_prefix()
    basename = posixpath.basename(candidate).lower()
    if basename not in _RESERVED_FIXTURE_KEYS:
        return
    relative = candidate[len(prefix) :] if prefix and candidate.startswith(prefix) else candidate
    if "/" in relative:
        return
    observability.log_event(
        logger,
        event="EVIDENCE_INVALID",
        field=field,
        key=candidate,
        error_code=EVIDENCE_INVALID,
        reason="reserved_fixture_key",
    )
    raise EvidenceError(
        EVIDENCE_INVALID,
        "A valid S3 evidence object is required. The reserved smoke-test key "
        f"{candidate!r} is not accepted in production.",
    )


def validate_evidence_key(key: Any, field: str = "s3_image_url") -> str:
    """Confirm an object key is well formed and inside the configured prefix."""
    candidate = key.strip() if isinstance(key, str) else ""
    if not candidate:
        raise EvidenceError(
            EVIDENCE_INVALID,
            "A valid S3 evidence object is required.",
        )
    if len(candidate) > MAX_KEY_LENGTH:
        raise EvidenceError(EVIDENCE_INVALID_KEY, f"{field} is too long")

    if candidate.startswith("/") or ".." in candidate:
        raise EvidenceError(EVIDENCE_INVALID_KEY, f"{field} is not a valid object key")
    if posixpath.normpath(candidate) != candidate:
        raise EvidenceError(EVIDENCE_INVALID_KEY, f"{field} is not a valid object key")
    if "\\" in candidate or any(character < " " for character in candidate):
        raise EvidenceError(EVIDENCE_INVALID_KEY, f"{field} is not a valid object key")

    prefix = config.evidence_key_prefix()
    if prefix and not candidate.startswith(prefix):
        raise EvidenceError(
            EVIDENCE_INVALID_KEY,
            f"{field} must point at an object under {prefix}",
        )
    _reject_reserved_fixture(candidate, field)
    return candidate


def assert_bucket(bucket: Any) -> str:
    """Refuse a bucket that is not the configured evidence bucket."""
    expected = config.bucket_name()
    supplied = bucket.strip() if isinstance(bucket, str) else ""
    if not supplied:
        return expected
    if supplied != expected:
        raise EvidenceError(
            EVIDENCE_BUCKET_MISMATCH,
            "The supplied evidence belongs to a different S3 bucket.",
        )
    return expected


def _classify_s3_error(exc: ClientError, key: str, operation: str) -> EvidenceError:
    error = exc.response.get("Error") or {}
    api_code = str(error.get("Code") or "")
    message = str(error.get("Message") or exc)
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    combined = f"{api_code} {message}".lower()

    observability.log_event(
        logger,
        event="EVIDENCE_DOWNLOAD_FAILED" if operation == "GetObject" else "EVIDENCE_HEAD_OBJECT_FAILED",
        bucket=config.bucket_name(),
        key=key,
        operation=operation,
        error_code=api_code or str(status),
        http_status=status,
    )

    if "kms" in combined:
        return EvidenceError(
            EVIDENCE_KMS_ACCESS_DENIED,
            "The evidence object is KMS-encrypted and this function cannot decrypt it. "
            "Set EvidenceKmsKeyArn on deploy if the bucket uses a customer-managed key.",
        )
    if api_code in {"NoSuchKey", "NotFound"} or status == 404:
        return EvidenceError(
            EVIDENCE_NOT_FOUND,
            "No object found at the supplied key. Complete the upload before submitting the claim.",
        )
    if api_code in {"AccessDenied", "AccessDeniedException", "403"} or status == 403:
        return EvidenceError(
            EVIDENCE_ACCESS_DENIED,
            "Access denied reading the evidence object. Confirm the Lambda role is allowed "
            "s3:GetObject on this bucket/prefix (a missing object can also appear as 403 "
            "because this role has no s3:ListBucket).",
        )
    return EvidenceError(
        EVIDENCE_DOWNLOAD_FAILED,
        f"S3 {operation} failed ({api_code or status}): {message[:200]}",
    )


def head_object(key: str) -> Dict[str, Any]:
    """Head the object. Returns size and content_type. Refuses empty objects."""
    bucket = config.bucket_name()
    observability.log_event(
        logger,
        event="EVIDENCE_HEAD_OBJECT_STARTED",
        bucket=bucket,
        key=key,
        region=config.aws_region(),
    )
    try:
        head = _client().head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        raise _classify_s3_error(exc, key, "HeadObject") from exc

    size = int(head.get("ContentLength") or 0)
    content_type = str(head.get("ContentType") or "")
    observability.log_event(
        logger,
        event="EVIDENCE_HEAD_OBJECT_SUCCESS",
        bucket=bucket,
        key=key,
        content_length=size,
        content_type=content_type or None,
    )
    if size <= 0:
        raise EvidenceError(EVIDENCE_EMPTY, "Evidence object is empty (0 bytes)")
    return {"bucket": bucket, "key": key, "content_length": size, "content_type": content_type}


def assert_object_exists(key: str) -> int:
    """Return the object's size, refusing missing, denied, or empty objects."""
    return int(head_object(key)["content_length"])


def download_object(key: str, destination: str, bucket: Optional[str] = None) -> Dict[str, Any]:
    """Download via s3:GetObject. Never HTTP-fetches a URL.

    Bucket and key are re-validated here so a hostile Step Functions payload
    cannot make Agent 1 GetObject an arbitrary object.
    """
    expected = assert_bucket(bucket)
    validated = validate_evidence_key(key, field="evidence.key")
    observability.log_event(
        logger,
        event="EVIDENCE_DOWNLOAD_STARTED",
        bucket=expected,
        key=validated,
        region=config.aws_region(),
    )
    logger.info("Downloading s3://%s/%s", expected, validated)
    try:
        _client().download_file(expected, validated, destination)
    except ClientError as exc:
        raise _classify_s3_error(exc, validated, "GetObject") from exc
    except Exception as exc:
        observability.log_event(
            logger,
            event="EVIDENCE_DOWNLOAD_FAILED",
            bucket=expected,
            key=validated,
            operation="GetObject",
            error_code=type(exc).__name__,
        )
        raise EvidenceError(
            EVIDENCE_DOWNLOAD_FAILED,
            "Failed to download the evidence object from S3.",
        ) from exc

    observability.log_event(
        logger,
        event="EVIDENCE_DOWNLOAD_SUCCESS",
        bucket=expected,
        key=validated,
    )
    return {"bucket": expected, "key": validated}
