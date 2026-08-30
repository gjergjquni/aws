"""Configuration accessors.

Every value is read from the environment on each call rather than captured at
import time, so a configuration change takes effect on the next invocation
instead of waiting for the container to be recycled.
"""

from __future__ import annotations

import logging
import os

from .errors import ConfigError

# Nova models reject the bare foundation-model ID for on-demand invocation and
# require a cross-region inference profile. See README "Bedrock model access".
DEFAULT_MODEL_ID = "us.amazon.nova-pro-v1:0"

FRAUD_PATTERN_DOCUMENTS_FILENAME = "fraud_pattern_documents.json"

# Legacy aggregator values. Agents also emit the investigation-contract values
# below; the aggregator maps both sets.
RECOMMENDATIONS = ("clear", "review", "escalate")

VISUAL_RECOMMENDATIONS = (
    "NO_ADDITIONAL_ACTION",
    "REVIEW_EVIDENCE",
    "MANUAL_INVESTIGATION",
)
CLAIM_RECOMMENDATIONS = (
    "NO_ADDITIONAL_ACTION",
    "REVIEW_CLAIM",
    "MANUAL_INVESTIGATION",
)
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
SEVERITIES = ("LOW", "MEDIUM", "HIGH")

DEFAULT_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
DEFAULT_EMBEDDING_DIMENSIONS = 1024
DEFAULT_OPENSEARCH_INDEX = "aegis-fraud-patterns"
DEFAULT_VECTOR_THRESHOLD = 0.72
MAX_EVIDENCE_IMAGES = 5

# What the frontend contract publishes today. Not a whitelist: intake accepts any
# category and logs the ones outside this set, so a new product line can never
# fail a fraud check and the list gets extended deliberately rather than drifting.
PRODUCT_CATEGORIES = ("electronics", "clothing", "other")


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Required environment variable {name} is not set")
    return value


def _optional(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer, got {raw!r}") from exc


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be a number, got {raw!r}") from exc


def table_name() -> str:
    return _require("DYNAMODB_TABLE")


def table_name_optional() -> str:
    """Empty when running locally without DynamoDB persistence."""
    return os.environ.get("DYNAMODB_TABLE", "").strip()


def bucket_name() -> str:
    """Bucket holding evidence photos. Owned and written by the upload service."""
    return _require("EVIDENCE_BUCKET")


def allow_evidence_fixtures() -> bool:
    """Local/demo only. Production must never accept uploads/test.jpg as evidence."""
    return os.environ.get("ALLOW_EVIDENCE_FIXTURES", "").strip().lower() in {"1", "true", "yes"}


def evidence_key_prefix() -> str:
    """Prefix every accepted object key must start with.

    Canonical env var is EVIDENCE_PREFIX; EVIDENCE_KEY_PREFIX is the deploy alias
    already wired in template.yaml. A non-empty value always ends with ``/`` so
    ``uploads`` cannot accidentally match ``uploads-secret/...``. Empty means any
    key in the bucket (must stay aligned with the IAM resource ARN).
    """
    raw = os.environ.get("EVIDENCE_PREFIX", os.environ.get("EVIDENCE_KEY_PREFIX", "uploads/"))
    prefix = (raw or "").strip()
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix


def state_machine_arn() -> str:
    return _require("STATE_MACHINE_ARN")


def model_id() -> str:
    return _optional("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)


DEFAULT_HIVE_SYNC_URL = "https://api.thehive.ai/api/v3/hive/ai-generated-and-deepfake-content-detection"


def hive_secret_id() -> str:
    """ARN or name of the Secrets Manager secret holding the Hive API key.

    Empty when Hive checks are intentionally disabled.
    """
    return os.environ.get("HIVE_SECRET_ID", "").strip()


def hive_sync_url() -> str:
    """Hive V3 AI-generated / deepfake endpoint."""
    return _optional("HIVE_SYNC_URL", DEFAULT_HIVE_SYNC_URL)


def hive_moderation_threshold() -> float:
    """Confidence at which a Hive visual class becomes an Agent 1 finding."""
    return min(1.0, max(0.0, _float("HIVE_MODERATION_THRESHOLD", 0.9)))


def hive_max_retries() -> int:
    """Extra attempts after the first request, for 429/5xx only."""
    return max(0, min(4, _int("HIVE_MAX_RETRIES", 2)))


def allowed_origin() -> str:
    return _optional("ALLOWED_ORIGIN", "*")


def claim_ttl_days() -> int:
    """Days before a claim self-deletes. 0 disables expiry (the default)."""
    return max(0, _int("CLAIM_TTL_DAYS", 0))


def max_customer_text_chars() -> int:
    return _int("MAX_CUSTOMER_TEXT_CHARS", 8000)


def bedrock_read_timeout() -> int:
    """Kept below each function's Lambda timeout so botocore fails first.

    A botocore timeout produces a logged error and a retryable exception; a
    Lambda timeout kills the process with no diagnostic beyond a truncated log.
    """
    return _int("BEDROCK_READ_TIMEOUT", 40)


def bedrock_max_tokens() -> int:
    return _int("BEDROCK_MAX_TOKENS", 2048)


def hive_timeout_seconds() -> int:
    return _int("HIVE_TIMEOUT_SECONDS", 20)


def escalate_threshold() -> int:
    return _int("ESCALATE_THRESHOLD", 70)


def review_threshold() -> int:
    return _int("REVIEW_THRESHOLD", 40)


def confidence_threshold() -> float:
    """Agent 6 auto-decides FRAUD / NOT_FRAUD at or above this confidence.

    Default 0.80. Below this, Agent 6 requires human review. At or above it,
    Agent 6 may auto-decide FRAUD (deny refund) or NOT_FRAUD (allow refund).
    """
    return max(0.5, min(0.99, _float("CONFIDENCE_THRESHOLD", 0.80)))


def review_index_name() -> str:
    return _optional("REVIEW_INDEX_NAME", "review-status-index")


def visual_weight() -> float:
    """Agent 6 visual share of the combined score. Must sum with claim_weight to 1.0."""
    return agent6_weights()[0]


def claim_weight() -> float:
    """Agent 6 claim-intelligence share of the combined score."""
    return agent6_weights()[1]


def agent6_weights() -> tuple[float, float]:
    """Return (visual, claim) weights. Defaults 0.60 / 0.40.

    VISUAL_WEIGHT / CLAIM_WEIGHT are canonical. VISUAL_WEIGHT_PCT is a legacy
    alias (percentage 0-100) used only when VISUAL_WEIGHT is unset.
    """
    visual_raw = os.environ.get("VISUAL_WEIGHT", "").strip()
    claim_raw = os.environ.get("CLAIM_WEIGHT", "").strip()
    pct_raw = os.environ.get("VISUAL_WEIGHT_PCT", "").strip()

    if visual_raw:
        visual = _float("VISUAL_WEIGHT", 0.60)
    elif pct_raw:
        visual = _int("VISUAL_WEIGHT_PCT", 60) / 100.0
    else:
        visual = 0.60

    if claim_raw:
        claim = _float("CLAIM_WEIGHT", 0.40)
    else:
        claim = round(1.0 - visual, 4)

    if visual < 0 or visual > 1 or claim < 0 or claim > 1:
        raise ConfigError("VISUAL_WEIGHT and CLAIM_WEIGHT must be between 0 and 1")
    if abs(visual + claim - 1.0) > 0.001:
        raise ConfigError(
            f"VISUAL_WEIGHT ({visual}) + CLAIM_WEIGHT ({claim}) must equal 1.0"
        )
    return visual, claim


def embedding_model_id() -> str:
    return _optional("BEDROCK_EMBEDDING_MODEL_ID", DEFAULT_EMBEDDING_MODEL_ID)


def embedding_dimensions() -> int:
    return _int("BEDROCK_EMBEDDING_DIMENSIONS", DEFAULT_EMBEDDING_DIMENSIONS)


def opensearch_endpoint() -> str:
    """Empty means OpenSearch is not configured; Agent 2 uses in-memory retrieval."""
    return os.environ.get("OPENSEARCH_ENDPOINT", "").strip().rstrip("/")


def opensearch_index() -> str:
    return _optional("OPENSEARCH_INDEX", DEFAULT_OPENSEARCH_INDEX)


def vector_similarity_threshold() -> float:
    return max(0.0, min(1.0, _float("VECTOR_SIMILARITY_THRESHOLD", DEFAULT_VECTOR_THRESHOLD)))


def rekognition_max_labels() -> int:
    return _int("REKOGNITION_MAX_LABELS", 20)


def rekognition_min_confidence() -> float:
    return max(0.0, min(100.0, _float("REKOGNITION_MIN_CONFIDENCE", 70.0)))


def max_evidence_images() -> int:
    return max(1, min(10, _int("MAX_EVIDENCE_IMAGES", MAX_EVIDENCE_IMAGES)))


def max_image_bytes() -> int:
    """Reject evidence files larger than this before decoding. Default 15 MB."""
    return _int("MAX_IMAGE_BYTES", 15 * 1024 * 1024)


def persist_results() -> bool:
    return bool(table_name_optional())


def aws_region() -> str:
    return _optional("AWS_REGION", "us-east-1")


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(_optional("LOG_LEVEL", "INFO").upper())
    return logger
