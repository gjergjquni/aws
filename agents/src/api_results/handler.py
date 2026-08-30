"""GET /results/{claimId} — the frontend's polling endpoint.

Kept as its own function so read traffic never queues behind the analysis
Lambdas, and so it holds nothing but a DynamoDB Query permission. Poll until
``complete`` is true; while it is false the agent entries fill in one at a time
as each finishes.

A claim whose workflow died without reaching the aggregator would otherwise sit
at ``processing`` forever and the UI would poll indefinitely, so a claim still
processing well past the worst-case runtime is reported as failed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from shared import config, dynamodb_client, http
from shared.errors import NotFoundError

logger = config.get_logger(__name__)

_TERMINAL = {
    dynamodb_client.STATUS_COMPLETE,
    dynamodb_client.STATUS_FAILED,
    dynamodb_client.STATUS_PENDING_REVIEW,
}

# Comfortably beyond the visual agent's 180s timeout times three retries.
STALE_AFTER_SECONDS = 900


def _age_seconds(timestamp: Optional[str]) -> Optional[float]:
    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        created = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds()


@http.api_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    path_params = event.get("pathParameters") or {}
    claim_id = http.validate_claim_id(path_params.get("claimId"))

    claim = dynamodb_client.get_claim(claim_id)
    if claim is None:
        raise NotFoundError(f"No claim found with id {claim_id}")

    if claim["status"] not in _TERMINAL:
        age = _age_seconds(claim.get("created_at"))
        if age is not None and age > STALE_AFTER_SECONDS:
            logger.warning("Claim %s still processing after %.0fs; reporting failed", claim_id, age)
            claim["status"] = dynamodb_client.STATUS_FAILED
            claim["note"] = "Analysis did not finish in the expected time"

    claim["complete"] = claim["status"] in _TERMINAL
    return http.response(200, claim)
