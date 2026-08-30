"""Canonical evidence contract: one {bucket, key} for the whole pipeline.

Intake and /analyze accept several external aliases, normalize immediately,
and put the result on the Step Functions input as ``evidence``. Agent 1 reads
that object and calls ``s3.download_file(bucket, key, path)``. It does not
re-parse HTTP URLs.

Aliases accepted (then discarded):

    s3_image_url, s3_url, s3_key, image_url
    s3ImageUrl, s3Url, s3Key, imageUrl
    evidence.url / evidence.key / evidence.s3_image_url / ...
    evidence as a string URL

Unrecognized image-like fields are rejected with the field name, not ignored.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import config, observability, s3_utils
from .errors import EVIDENCE_INVALID, EVIDENCE_MISSING, EvidenceError

logger = config.get_logger(__name__)

# Documented external aliases, in lookup order.
_TOP_LEVEL_FIELDS: Tuple[str, ...] = (
    "s3_image_url",
    "s3_url",
    "s3_key",
    "image_url",
    "s3ImageUrl",
    "s3Url",
    "s3Key",
    "imageUrl",
)

_NESTED_FIELDS: Tuple[str, ...] = (
    "s3_image_url",
    "s3_url",
    "s3_key",
    "image_url",
    "url",
    "key",
)

_LIST_FIELDS: Tuple[str, ...] = (
    "s3_image_urls",
    "s3_urls",
    "s3_keys",
    "s3ImageUrls",
    "s3Urls",
    "s3Keys",
    "image_urls",
)

_IMAGE_LIKE_FIELD = re.compile(
    r"(image|photo|picture|s3|evidence|upload|file|media).*(url|key|uri|href)|"
    r"^(url|key|uri|href|photo|image)$",
    re.IGNORECASE,
)

_KNOWN_IMAGE_FIELDS = set(_TOP_LEVEL_FIELDS) | set(_LIST_FIELDS) | {"evidence"}


def _nonempty_string(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _first_string(mapping: Dict[str, Any], names: Sequence[str]) -> Optional[str]:
    for name in names:
        text = _nonempty_string(mapping.get(name))
        if text:
            return text
    return None


def _unknown_image_fields(payload: Dict[str, Any]) -> List[str]:
    found: List[str] = []
    for key in payload:
        if key in _KNOWN_IMAGE_FIELDS:
            continue
        if _IMAGE_LIKE_FIELD.search(str(key)):
            found.append(str(key))
    nested = payload.get("evidence")
    if isinstance(nested, dict):
        for key in nested:
            if key in _NESTED_FIELDS or key in {"bucket", "keys"}:
                continue
            if _IMAGE_LIKE_FIELD.search(str(key)):
                found.append(f"evidence.{key}")
    return found


def extract_raw_references(payload: Dict[str, Any]) -> List[Any]:
    """Pull every recognized image reference out of a request body, in order."""
    refs: List[Any] = []
    nested = payload.get("evidence")
    if isinstance(nested, str) and nested.strip():
        refs.append(nested.strip())
    elif isinstance(nested, dict):
        if nested.get("bucket"):
            s3_utils.assert_bucket(nested.get("bucket"))
        nested_ref = _first_string(nested, _NESTED_FIELDS)
        if nested_ref:
            refs.append(nested_ref)
        extra = nested.get("keys") or nested.get("urls")
        if isinstance(extra, list):
            refs.extend(item for item in extra if item)

    top = _first_string(payload, _TOP_LEVEL_FIELDS)
    if top:
        refs.append(top)

    for list_name in _LIST_FIELDS:
        extra = payload.get(list_name)
        if isinstance(extra, list):
            refs.extend(item for item in extra if item)
        elif extra:
            refs.append(extra)

    return refs


def _empty_image_field(payload: Dict[str, Any]) -> Optional[str]:
    """Return the name of an image field that is present but blank."""
    for name in _TOP_LEVEL_FIELDS:
        value = payload.get(name)
        if isinstance(value, str) and not value.strip():
            return name
    nested = payload.get("evidence")
    if isinstance(nested, str) and not nested.strip():
        return "evidence"
    if isinstance(nested, dict):
        for name in _NESTED_FIELDS:
            value = nested.get(name)
            if isinstance(value, str) and not value.strip():
                return f"evidence.{name}"
    return None


def normalize_many(raw_values: Sequence[Any], *, field: str = "s3_image_url") -> List[Dict[str, str]]:
    seen: set[str] = set()
    items: List[Dict[str, str]] = []
    limit = config.max_evidence_images()
    for value in raw_values:
        normalized = s3_utils.normalize_evidence_reference(value, field=field)
        if normalized["key"] in seen:
            continue
        seen.add(normalized["key"])
        items.append(normalized)
        if len(items) >= limit:
            break
    return items


def from_payload(payload: Dict[str, Any], *, required: bool = True, field: str = "s3_image_url") -> List[Dict[str, str]]:
    """Normalize every image reference on a JSON body. Never silently drop unknown fields."""
    observability.log_event(logger, event="EVIDENCE_RECEIVED", field=field)
    raw = extract_raw_references(payload)
    unknown = _unknown_image_fields(payload) if not raw else []
    if not raw:
        empty_field = _empty_image_field(payload)
        if empty_field:
            raise EvidenceError(
                EVIDENCE_INVALID,
                "A valid S3 evidence object is required.",
            )
        if unknown:
            raise EvidenceError(
                EVIDENCE_MISSING,
                (
                    f"Unrecognized image field {unknown[0]!r}. "
                    f"Send {field} (aliases: s3_url, s3_key, image_url, or evidence.url / evidence.key)."
                ),
            )
        if required:
            raise EvidenceError(
                EVIDENCE_MISSING,
                (
                    f"Missing required field: {field}. "
                    "Aliases: s3_url, s3_key, image_url, evidence.url, evidence.key. "
                    "Value must be s3://bucket/key, an S3 HTTPS URL, a presigned S3 GET URL, "
                    "or a bare key under the configured prefix."
                ),
            )
        return []
    return normalize_many(raw, field=field)


def from_event(event: Dict[str, Any]) -> List[Dict[str, str]]:
    """Read already-normalized evidence from Step Functions, with a legacy fallback.

    Agent 1 must not re-parse the original HTTP URL when ``evidence`` is present.
    """
    items: List[Dict[str, str]] = []
    block = event.get("evidence")
    if isinstance(block, dict) and (block.get("key") or block.get("keys")):
        bucket = s3_utils.assert_bucket(block.get("bucket"))
        keys: List[str] = []
        if block.get("key"):
            keys.append(s3_utils.validate_evidence_key(block.get("key"), field="evidence.key"))
        extra = block.get("keys") or []
        if isinstance(extra, list):
            for item in extra:
                if isinstance(item, dict) and item.get("key"):
                    keys.append(s3_utils.validate_evidence_key(item.get("key"), field="evidence.key"))
                elif item:
                    keys.append(s3_utils.validate_evidence_key(item, field="evidence.key"))
        seen: set[str] = set()
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            items.append({"bucket": bucket, "key": key})
        if items:
            return items[: config.max_evidence_images()]

    # Legacy flattened fields (in-flight executions, local demo).
    return from_payload(event, required=True, field="s3_image_url")


def canonical_uri(item: Dict[str, str]) -> str:
    return f"s3://{item['bucket']}/{item['key']}"


def workflow_payload(
    *,
    claim_id: str,
    evidence_items: Sequence[Dict[str, str]],
    product_category: str,
    customer_claimed_condition: str,
    customer_text: str,
    order_value_usd: float,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Step Functions input: nested claim + evidence, plus flattened aliases."""
    items = list(evidence_items)
    primary = items[0]
    payload: Dict[str, Any] = {
        "claim_id": claim_id,
        "claim": {
            "claim_id": claim_id,
            "product_category": product_category,
            "customer_claimed_condition": customer_claimed_condition,
            "customer_text": customer_text,
            "order_value_usd": order_value_usd,
        },
        "evidence": {
            "bucket": primary["bucket"],
            "key": primary["key"],
            "keys": [item["key"] for item in items],
        },
        # Flattened aliases so in-flight / older task definitions keep working.
        "s3_key": primary["key"],
        "s3_keys": [item["key"] for item in items],
        "s3_url": canonical_uri(primary),
        "product_category": product_category,
        "customer_claimed_condition": customer_claimed_condition,
        "customer_text": customer_text,
        "message": customer_text,
        "order_value_usd": order_value_usd,
    }
    if extra:
        payload.update(extra)
        payload["claim"].update({k: v for k, v in extra.items() if k in payload["claim"]})
    return payload


def claim_fields(event: Dict[str, Any]) -> Dict[str, Any]:
    """Read claim context from nested ``claim`` or flattened event keys."""
    nested = event.get("claim") if isinstance(event.get("claim"), dict) else {}
    def pick(name: str, default: Any = "") -> Any:
        if nested.get(name) not in (None, ""):
            return nested[name]
        return event.get(name, default)

    return {
        "claim_id": str(pick("claim_id") or ""),
        "product_category": pick("product_category") or "unknown",
        "customer_claimed_condition": pick("customer_claimed_condition") or "",
        "customer_text": pick("customer_text") or pick("message") or "",
        "order_value_usd": pick("order_value_usd", 0),
    }
