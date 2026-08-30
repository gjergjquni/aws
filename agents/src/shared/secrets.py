"""Secrets Manager access, cached for the life of the container.

The cache means one API call per cold start rather than one per invocation.
Lambda reads secrets with IAM ``secretsmanager:GetSecretValue`` via boto3.
The AWS Parameters and Secrets Lambda extension (localhost:2773) is not used.
Rotating a secret therefore takes effect as containers recycle; force it sooner
by publishing a new function version or updating any environment variable.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from . import aws, config
from .errors import HIVE_CONFIGURATION_ERROR, HIVE_CREDENTIAL_CONFIGURATION_REQUIRED

logger = config.get_logger(__name__)

_cache: Dict[str, Optional[str]] = {}

# Hive V3 Playground auth is ``Authorization: Bearer <SECRET_KEY>``.
# Field names "api_key", "api key", and "Secret Key" all resolve to that Bearer token.
_HIVE_API_KEY_FIELDS = (
    "api_key",
    "api key",
    "hive_api_key",
    "API_KEY",
    "token",
    "secret_key",
    "Secret Key",
    "visual_api_key",
    "va1_api_key",
)

_HIVE_NESTED_VISUAL = ("va1", "VA1", "visual", "visual_moderation")
_ACCESS_KEY_FIELDS = {
    "access_key_id",
    "accesskeyid",
    "access_key",
    "aws_access_key_id",
    "Access Key ID",
}
_SECRET_KEY_FIELDS = {
    "secret_key",
    "secretkey",
    "aws_secret_access_key",
    "Secret Key",
}


def _fetch(secret_id: str) -> Optional[str]:
    client = aws.client("secretsmanager", read_timeout=10)
    payload = client.get_secret_value(SecretId=secret_id)
    return payload.get("SecretString")


def _raw_secret(secret_id: str) -> Optional[str]:
    if not secret_id:
        return None
    if secret_id not in _cache:
        try:
            _cache[secret_id] = _fetch(secret_id)
        except Exception as exc:
            logger.warning("Could not read secret %s: %s", secret_id, type(exc).__name__)
            _cache[secret_id] = None
    return _cache[secret_id]


def get_secret_document(secret_id: str) -> Optional[Any]:
    """Parse the secret JSON. Never logs values."""
    raw = _raw_secret(secret_id)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip() or None


def get_secret_field(secret_id: str, field: str) -> Optional[str]:
    """Read one field from a JSON secret, or None if unavailable.

    Returns None rather than raising: callers of this module treat their secret
    as optional and degrade gracefully when it is missing.
    """
    document = get_secret_document(secret_id)
    if document is None:
        return None
    if isinstance(document, str):
        return document
    if not isinstance(document, dict):
        return None
    value = document.get(field)
    return value.strip() if isinstance(value, str) and value.strip() else None


def secret_field_names(secret_id: str) -> List[str]:
    """Safe: names only, never values."""
    document = get_secret_document(secret_id)
    if isinstance(document, dict):
        return sorted(str(key) for key in document.keys())
    if isinstance(document, str):
        return ["<plaintext>"]
    return []


def _canonical_field_name(name: str) -> str:
    return " ".join(name.strip().lower().replace("-", " ").split()).replace(" ", "_")


def _string_field(mapping: Dict[str, Any], names: Tuple[str, ...]) -> Optional[str]:
    canon = {_canonical_field_name(str(key)): value for key, value in mapping.items()}
    wanted = [_canonical_field_name(name) for name in names]
    for name in wanted:
        value = canon.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for name in names:
        value = mapping.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _looks_like_access_secret_pair(mapping: Dict[str, Any]) -> bool:
    keys = set(mapping.keys())
    has_access = bool(keys & _ACCESS_KEY_FIELDS)
    has_secret = bool(keys & _SECRET_KEY_FIELDS)
    return has_access and has_secret


def resolve_hive_api_key(document: Any) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Return (api_key, error_code, field_names_present).

    Prefers VA1 / visual fields over SF1 when both contain an api_key.
    """
    if isinstance(document, str) and document.strip():
        return document.strip(), None, ["<plaintext>"]
    if not isinstance(document, dict):
        return None, HIVE_CONFIGURATION_ERROR, []

    names = sorted(str(key) for key in document.keys())
    direct = _string_field(document, _HIVE_API_KEY_FIELDS)
    if direct:
        return direct, None, names

    for nested_name in _HIVE_NESTED_VISUAL:
        nested = document.get(nested_name)
        if isinstance(nested, str) and nested.strip() and nested_name.lower() in {"va1", "visual"}:
            return nested.strip(), None, names
        if isinstance(nested, dict):
            nested_key = _string_field(nested, _HIVE_API_KEY_FIELDS)
            if nested_key:
                return nested_key, None, names

    # SF1 is not used for Agent 1 visual moderation. If only SF1 has api_key, refuse.
    for speech_name in ("sf1", "SF1", "speech"):
        nested = document.get(speech_name)
        if isinstance(nested, dict) and _string_field(nested, _HIVE_API_KEY_FIELDS):
            return None, HIVE_CREDENTIAL_CONFIGURATION_REQUIRED, names
        if isinstance(nested, str) and nested.strip():
            return None, HIVE_CREDENTIAL_CONFIGURATION_REQUIRED, names

    if _looks_like_access_secret_pair(document):
        return None, HIVE_CREDENTIAL_CONFIGURATION_REQUIRED, names

    return None, HIVE_CONFIGURATION_ERROR if document else None, names


def get_hive_api_key() -> Optional[str]:
    """Hive V3 Secret Key used as Bearer token, or None. Never logs the value."""
    secret_id = config.hive_secret_id()
    if not secret_id:
        return None
    key, _code, _names = resolve_hive_api_key(get_secret_document(secret_id))
    return key


def get_hive_credentials() -> Dict[str, Any]:
    """Structured Hive credential lookup for Agent 1. Values are never included."""
    secret_id = config.hive_secret_id()
    if not secret_id:
        return {"ok": False, "api_key": None, "error_code": None, "fields": [], "reason": "HIVE_SECRET_ID is not set"}
    document = get_secret_document(secret_id)
    if document is None:
        return {
            "ok": False,
            "api_key": None,
            "error_code": HIVE_CONFIGURATION_ERROR,
            "fields": [],
            "reason": "Hive secret could not be read",
        }
    key, error_code, names = resolve_hive_api_key(document)
    if key:
        return {"ok": True, "api_key": key, "error_code": None, "fields": names, "reason": None}
    reason = (
        "HIVE_CREDENTIAL_CONFIGURATION_REQUIRED: the secret does not contain a Hive "
        "V3 Secret Key usable as Authorization: Bearer <SECRET_KEY>. "
        'Store {"api_key": "<Hive Secret Key>"} (spaces in the field name are OK). '
        f"Present fields: {names}."
    )
    return {
        "ok": False,
        "api_key": None,
        "error_code": error_code or HIVE_CONFIGURATION_ERROR,
        "fields": names,
        "reason": reason,
    }
