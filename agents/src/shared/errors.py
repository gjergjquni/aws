"""Exception hierarchy shared by every Lambda.

The distinction that matters operationally is between ``RetryableAgentError``
and everything else. Agent handlers raise the former (and only the former) so
the Step Functions retry policy can back off and try again; every other failure
is recorded against the claim and returned as a ``failed`` agent result, which
lets the pipeline produce a partial verdict instead of losing the other agent's
work.
"""

from __future__ import annotations


class AegisError(Exception):
    """Base class for all application errors."""


class ConfigError(AegisError):
    """A required environment variable is missing or malformed."""


class ValidationError(AegisError):
    """Caller-supplied input is invalid. Surfaces as HTTP 400."""

    code = "validation_error"

    def __init__(self, message: str = "", code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class NotFoundError(AegisError):
    """Requested resource does not exist. Surfaces as HTTP 404."""

    code = "not_found"


class ConflictError(AegisError):
    """Resource already exists. Surfaces as HTTP 409."""

    code = "conflict"


class RetryableAgentError(AegisError):
    """A transient failure worth retrying (throttling, timeouts, 5xx)."""


class BedrockInvocationError(AegisError):
    """Bedrock rejected the request or returned unusable output."""


class SchemaError(AegisError):
    """Model or tool output did not match the required structured schema."""


# ---------------------------------------------------------------------------
# Evidence pipeline — never collapse these into a generic "cannot read image"
# ---------------------------------------------------------------------------

EVIDENCE_MISSING = "EVIDENCE_MISSING"
EVIDENCE_INVALID = "EVIDENCE_INVALID"
EVIDENCE_INVALID_URL = "EVIDENCE_INVALID_URL"
EVIDENCE_BUCKET_MISMATCH = "EVIDENCE_BUCKET_MISMATCH"
EVIDENCE_INVALID_KEY = "EVIDENCE_INVALID_KEY"
EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
EVIDENCE_ACCESS_DENIED = "EVIDENCE_ACCESS_DENIED"
EVIDENCE_KMS_ACCESS_DENIED = "EVIDENCE_KMS_ACCESS_DENIED"
EVIDENCE_EMPTY = "EVIDENCE_EMPTY"
EVIDENCE_DOWNLOAD_FAILED = "EVIDENCE_DOWNLOAD_FAILED"
EVIDENCE_INVALID_IMAGE = "EVIDENCE_INVALID_IMAGE"
EVIDENCE_UNSUPPORTED_FORMAT = "EVIDENCE_UNSUPPORTED_FORMAT"

# Hive V3 AI-generated/deepfake — Agent 1 continues without Hive on these; they are logged.
HIVE_AUTH_FAILED = "HIVE_AUTH_FAILED"
HIVE_BAD_REQUEST = "HIVE_BAD_REQUEST"
HIVE_RATE_LIMITED = "HIVE_RATE_LIMITED"
HIVE_SERVER_ERROR = "HIVE_SERVER_ERROR"
HIVE_TIMEOUT = "HIVE_TIMEOUT"
HIVE_INVALID_RESPONSE = "HIVE_INVALID_RESPONSE"
HIVE_NO_RESULT = "HIVE_NO_RESULT"
HIVE_UNSUPPORTED_MEDIA = "HIVE_UNSUPPORTED_MEDIA"
HIVE_CONFIGURATION_ERROR = "HIVE_CONFIGURATION_ERROR"
HIVE_CREDENTIAL_CONFIGURATION_REQUIRED = "HIVE_CREDENTIAL_CONFIGURATION_REQUIRED"


class EvidenceError(ValidationError):
    """Typed failure on the S3/image path. APIs return 400 with this code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message, code=code)
