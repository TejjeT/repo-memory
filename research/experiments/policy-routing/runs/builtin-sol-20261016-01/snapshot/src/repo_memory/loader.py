"""Load Engineering Assertions from JSON documents."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .models import EngineeringAssertion, Provenance, Scope, Target, tupleize


def load_assertion(path: str | Path, schema_path: str | Path) -> EngineeringAssertion:
    """Validate and deserialize a JSON engineering assertion."""

    path = Path(path)
    schema_path = Path(schema_path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(raw)
    return assertion_from_dict(raw)


def assertion_from_dict(raw: dict[str, Any]) -> EngineeringAssertion:
    """Deserialize a validated assertion dictionary."""

    provenance = tuple(
        Provenance(
            type=item["type"],
            uri=item["uri"],
            revision=item.get("revision"),
            access_policy_ref=item.get("access_policy_ref"),
            last_validated_at=_parse_datetime(item.get("last_validated_at")),
        )
        for item in raw["provenance"]
    )
    targets = tuple(
        Target(kind=item["kind"], id=item["id"])
        for item in raw.get("applies_to", [])
    )

    created_at = _parse_datetime(raw["created_at"], required=True)
    assert created_at is not None

    return EngineeringAssertion(
        id=raw["id"],
        type=raw["type"],
        content=raw["content"],
        rationale=raw.get("rationale"),
        scope=Scope(**raw["scope"]),
        applies_to=targets,
        status=raw["status"],
        importance=raw["importance"],
        confidence=raw.get("confidence"),
        owner=raw.get("owner"),
        provenance=provenance,
        effective_from=_parse_datetime(raw.get("effective_from")),
        review_after=_parse_datetime(raw.get("review_after")),
        expires_at=_parse_datetime(raw.get("expires_at")),
        overrides=tupleize(raw.get("overrides")),
        supersedes=tupleize(raw.get("supersedes")),
        superseded_by=tupleize(raw.get("superseded_by")),
        conflicts_with=tupleize(raw.get("conflicts_with")),
        created_at=created_at,
    )


def _parse_datetime(value: str | None, *, required: bool = False) -> datetime | None:
    if value is None:
        if required:
            raise ValueError("required datetime value is missing")
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
