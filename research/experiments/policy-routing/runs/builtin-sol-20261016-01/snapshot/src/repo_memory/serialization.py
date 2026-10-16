"""Backend-neutral serialization for Engineering Assertions."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from .loader import assertion_from_dict
from .models import EngineeringAssertion


def assertion_to_dict(assertion: EngineeringAssertion) -> dict[str, Any]:
    """Serialize an assertion to a JSON-compatible dictionary."""

    raw = asdict(assertion)
    return _json_safe(raw)


def assertion_from_json_dict(raw: dict[str, Any]) -> EngineeringAssertion:
    """Deserialize an assertion dictionary.

    Validation remains the responsibility of the caller when the source is not
    trusted. Adapters may use this after reading canonical data they previously
    wrote.
    """

    return assertion_from_dict(raw)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
