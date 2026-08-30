"""Shared wrapper for the agent Step Functions tasks.

Failure policy, in one place because getting it inconsistent between agents
would be hard to notice:

* Transient failures re-raise, so the state machine's retry policy backs off and
  tries again. The failure is recorded first, so an exhausted retry still leaves
  an explanation on the claim.
* Terminal failures are recorded and returned as ``status: failed``. The branch
  completes, the other agent's work survives, and the aggregator produces a
  degraded verdict instead of the whole claim dying.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from . import config, dynamodb_client, http
from .errors import RetryableAgentError, ValidationError

logger = config.get_logger(__name__)


def agent_task(agent_key: str, response_key: str) -> Callable:
    def decorator(func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Callable:
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            nested = event.get("claim") if isinstance(event.get("claim"), dict) else {}
            claim_id = http.validate_claim_id(event.get("claim_id") or nested.get("claim_id"))
            logger.info("Agent %s starting for claim %s", response_key, claim_id)

            try:
                result = func(event)
            except RetryableAgentError as exc:
                if config.persist_results():
                    dynamodb_client.save_agent_failure(claim_id, agent_key, f"transient: {exc}")
                raise
            except ValidationError as exc:
                code = getattr(exc, "code", None) or "validation_error"
                message = f"{code}: {exc}"[:500]
                logger.warning("Agent %s rejected input for claim %s: %s", response_key, claim_id, message)
                if config.persist_results():
                    dynamodb_client.save_agent_failure(claim_id, agent_key, message)
                return {
                    "agent": response_key,
                    "status": "failed",
                    "result": None,
                    "error": message,
                    "error_code": code,
                }
            except Exception as exc:
                logger.exception("Agent %s failed terminally for claim %s", response_key, claim_id)
                message = str(exc)[:500]
                if config.persist_results():
                    dynamodb_client.save_agent_failure(claim_id, agent_key, message)
                return {
                    "agent": response_key,
                    "status": "failed",
                    "result": None,
                    "error": message,
                    "error_code": type(exc).__name__,
                }

            if config.persist_results():
                dynamodb_client.save_agent_result(claim_id, agent_key, result)
            else:
                logger.info("Skipping DynamoDB persist for %s (DYNAMODB_TABLE unset)", response_key)
            return {"agent": response_key, "status": "ok", "result": result, "error": None}

        wrapper.__name__ = getattr(func, "__name__", "handler")
        return wrapper

    return decorator
