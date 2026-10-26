"""Strict JSON parsing helpers for security-sensitive Observatory records."""
from __future__ import annotations

import json
from typing import Any


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous objects instead of silently accepting the last duplicate key."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def loads_strict(value: str) -> Any:
    """Parse JSON while rejecting duplicate keys at every object depth."""
    return json.loads(value, object_pairs_hook=_reject_duplicate_keys)
