"""Coercion helpers for untrusted values.

Used in two places: validating caller input at the API edge, and normalising
model output before it reaches DynamoDB or the frontend. A language model can
return a score of ``"85%"``, ``120``, or ``None`` for a field documented as an
integer 0-100, and the frontend contract has to hold regardless.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

TRUTHY = {"true", "yes", "1", "y"}
FALSEY = {"false", "no", "0", "n"}


def as_int(value: Any, default: int = 0, minimum: int = 0, maximum: int = 100) -> int:
    """Coerce to an int clamped into [minimum, maximum]."""
    try:
        if isinstance(value, bool):
            raise TypeError
        if isinstance(value, str):
            value = value.strip().rstrip("%")
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def as_float(
    value: Any, default: float = 0.0, minimum: float = 0.0, maximum: float = 1.0
) -> float:
    """Coerce to a float clamped into [minimum, maximum]."""
    try:
        if isinstance(value, bool):
            raise TypeError
        if isinstance(value, str):
            value = value.strip().rstrip("%")
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return max(minimum, min(maximum, number))


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in TRUTHY:
            return True
        if lowered in FALSEY:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def as_text(value: Any, default: str = "", max_length: int = 2000) -> str:
    if value is None:
        return default
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    if not text:
        return default
    return text[:max_length]


def as_choice(value: Any, choices: Iterable[str], default: str) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in choices:
            return lowered
    return default


def as_text_list(value: Any, max_items: int = 25, max_length: int = 500) -> List[str]:
    """Normalise to a list of non-empty strings, tolerating a bare string."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    items: List[str] = []
    for entry in value:
        text = as_text(entry, max_length=max_length)
        if text:
            items.append(text)
        if len(items) >= max_items:
            break
    return items


def optional_text(value: Any, max_length: int = 2000) -> Optional[str]:
    text = as_text(value, max_length=max_length)
    return text or None
