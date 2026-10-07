"""Tests for issue #4: memory_search and memory_get.

Covers the complete tool -> identity adapter -> context assembly ->
serialized response path: authentication fail-closed, per-caller differing
results, hidden existence of denied assertions, redaction markers, and the
MCP tool definitions/dispatcher.
"""

from datetime import UTC, datetime

import pytest

from repo_memory.auth import AuthenticationError, VerifiedSession
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.tools import (
    TOOL_DEFINITIONS,
    ToolError,
    handle_tool_call,
    memory_get,
    memory_search,
    parse_scope,
    serialize_assertion,
)

NOW = datetime(2026, 10, 7, tzinfo=UTC)

PUBLIC_SOURCE = (Provenance(type="document", uri="doc://handbook"),)
RESTRICTED_SOURCE = (
    Provenance(
        type="incident",
        uri="incident://restricted/7",
        revision="rev-9",
        access_policy_ref="incident-access",
    ),
)


class FakeDirectory:
    def __init__(self, grants: dict[str, tuple[str, ...]]) -> None:
        self._grants = grants

    def grants_for(self, subject: str) -> tuple[str, ...]:
        return self._grants[subject]


DIRECTORY = FakeDirectory({"alice": ("doc://", "incident://"), "bob": ("doc://",)})


def make_session(subject: str) -> VerifiedSession:
    return VerifiedSession(subject=subject, authenticated_at=NOW, method="test")


def make_assertion(
    assertion_id: str,
    provenance: tuple[Provenance, ...] = PUBLIC_SOURCE,
    scope: Scope | None = None,
) -> EngineeringAssertion:
    return EngineeringAssertion(
        id=assertion_id,
        type="constraint",
        content=f"content of {assertion_id}",
        scope=scope or Scope(organization="Acme"),
        status="approved",
        importance="high",
        provenance=provenance,
        created_at=NOW,
        rationale=f"rationale for {assertion_id}",
    )


CORPUS = (
    make_assertion("EA-PUBLIC", PUBLIC_SOURCE),
    make_assertion("EA-SECRET", RESTRICTED_SOURCE),
)

SCOPE = Scope(organization="Acme", repository="billing-api")


def test_memory_search_two_callers_differ():
    alice = memory_search(
        make_session("alice"), DIRECTORY, CORPUS, "deploy", SCOPE
    )
    bob = memory_search(make_session("bob"), DIRECTORY, CORPUS, "deploy", SCOPE)

    assert [a["id"] for a in alice["assertions"]] == ["EA-PUBLIC", "EA-SECRET"]
    assert [a["id"] for a in bob["assertions"]] == ["EA-PUBLIC"]
    # Redaction markers are explicit in the serialized provenance.
    (secret,) = [
        a for a in alice["assertions"] if a["id"] == "EA-SECRET"
    ]
    assert secret["provenance"][0]["redacted"] is False
    assert secret["rationale"] == "rationale for EA-SECRET"


def test_memory_search_denied_assertion_hidden():
    bob = memory_search(make_session("bob"), DIRECTORY, CORPUS, "deploy", SCOPE)
    payload = str(bob)
    assert "EA-SECRET" not in payload
    assert "incident://restricted/7" not in payload


def test_memory_search_missing_credentials_fail_closed():
    with pytest.raises(AuthenticationError):
        memory_search(None, DIRECTORY, CORPUS, "deploy", SCOPE)


def test_memory_search_rejects_empty_task_and_bad_budget():
    with pytest.raises(ToolError):
        memory_search(make_session("alice"), DIRECTORY, CORPUS, "  ", SCOPE)
    with pytest.raises(ToolError):
        memory_search(
            make_session("alice"), DIRECTORY, CORPUS, "deploy", SCOPE,
            evidence_budget=-1,
        )


def test_memory_get_permitted_returns_caller_safe_assertion():
    result = memory_get(make_session("alice"), DIRECTORY, CORPUS, "EA-SECRET")
    assertion = result["assertion"]
    assert assertion["id"] == "EA-SECRET"
    assert assertion["provenance"][0]["redacted"] is False
    assert assertion["provenance"][0]["uri"] == "incident://restricted/7"


def test_memory_get_denied_indistinguishable_from_missing():
    denied = None
    missing = None
    with pytest.raises(ToolError) as exc_info:
        memory_get(make_session("bob"), DIRECTORY, CORPUS, "EA-SECRET")
    denied = exc_info.value
    with pytest.raises(ToolError) as exc_info:
        memory_get(make_session("bob"), DIRECTORY, CORPUS, "EA-NOPE")
    missing = exc_info.value
    assert denied.code == missing.code == "not_found"
    assert denied.to_dict() == missing.to_dict()


def test_memory_get_missing_credentials_fail_closed():
    with pytest.raises(AuthenticationError):
        memory_get(None, DIRECTORY, CORPUS, "EA-PUBLIC")


def test_memory_get_respects_read_not_just_discovery():
    # Bob can read EA-PUBLIC; the payload carries no restricted material.
    result = memory_get(make_session("bob"), DIRECTORY, CORPUS, "EA-PUBLIC")
    assert result["assertion"]["id"] == "EA-PUBLIC"
    assert "incident" not in str(result)


def test_parse_scope_rejects_unknown_keys():
    with pytest.raises(ToolError):
        parse_scope({"organization": "Acme", "bogus": "x"})
    scope = parse_scope({"organization": "Acme", "repository": "billing-api"})
    assert scope == Scope(organization="Acme", repository="billing-api")


def test_serialize_assertion_marks_redaction():
    assertion = make_assertion("EA-1", RESTRICTED_SOURCE)
    payload = serialize_assertion(assertion)
    assert payload["provenance"][0]["redacted"] is False
    assert payload["provenance"][0]["uri"] == "incident://restricted/7"


def test_tool_definitions_cover_both_tools():
    names = [d["name"] for d in TOOL_DEFINITIONS]
    assert names == ["memory_search", "memory_get"]
    for definition in TOOL_DEFINITIONS:
        schema = definition["inputSchema"]
        assert schema["type"] == "object"
        assert "session_token" in schema["properties"]
        assert schema["required"]


def _resolve(token: str | None):
    subjects = {"alice-token": "alice", "bob-token": "bob"}
    if not token or token not in subjects:
        return None
    return VerifiedSession(
        subject=subjects[token], authenticated_at=NOW, method="test"
    )


def test_handle_tool_call_dispatches_search():
    payload = handle_tool_call(
        "memory_search",
        {
            "task": "deploy",
            "scope": {"organization": "Acme"},
            "session_token": "bob-token",
        },
        resolve_session=_resolve,
        directory=DIRECTORY,
        assertions=CORPUS,
    )
    assert [a["id"] for a in payload["assertions"]] == ["EA-PUBLIC"]


def test_handle_tool_call_dispatches_get():
    payload = handle_tool_call(
        "memory_get",
        {"assertion_id": "EA-PUBLIC", "session_token": "alice-token"},
        resolve_session=_resolve,
        directory=DIRECTORY,
        assertions=CORPUS,
    )
    assert payload["assertion"]["id"] == "EA-PUBLIC"


def test_handle_tool_call_bad_token_fails_closed_as_error():
    payload = handle_tool_call(
        "memory_search",
        {
            "task": "deploy",
            "scope": {"organization": "Acme"},
            "session_token": "bogus",
        },
        resolve_session=_resolve,
        directory=DIRECTORY,
        assertions=CORPUS,
    )
    assert payload["error"]["code"] == "unauthenticated"


def test_handle_tool_call_unknown_tool():
    with pytest.raises(ToolError):
        handle_tool_call(
            "memory_delete",
            {},
            resolve_session=_resolve,
            directory=DIRECTORY,
            assertions=CORPUS,
        )
