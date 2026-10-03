import json
from datetime import UTC, datetime
from typing import Any

from repo_memory.adapters.openviking import (
    OpenVikingAssertionStore,
    assertion_tags,
    assertion_uri,
)
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext

NOW = datetime(2026, 10, 3, tzinfo=UTC)
SOURCE = (Provenance(type="document", uri="test://source"),)


class FakeOpenVikingClient:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.options: dict[str, dict[str, Any]] = {}
        self.denied: set[str] = set()

    def write(
        self,
        uri: str,
        content: str,
        mode: str = "replace",
        options: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        assert mode == "replace"
        self.files[uri] = content
        self.options[uri] = options or {}
        return {"uri": uri}

    def read(self, uri: str) -> str:
        return self.files[uri]

    def ls(
        self,
        uri: str,
        simple: bool = False,
        recursive: bool = False,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        assert recursive is True
        return [
            {
                "uri": path,
                "name": path.rsplit("/", 1)[-1],
                "isDir": False,
                **({"access": "denied"} if path in self.denied else {}),
            }
            for path in sorted(self.files)
            if path.startswith(uri)
        ]


def make_assertion(
    assertion_id: str,
    *,
    scope: Scope,
    type: str = "constraint",
    status: str = "approved",
    importance: str = "high",
    overrides: tuple[str, ...] = (),
    supersedes: tuple[str, ...] = (),
) -> EngineeringAssertion:
    return EngineeringAssertion(
        id=assertion_id,
        type=type,
        content=assertion_id,
        scope=scope,
        status=status,
        importance=importance,
        provenance=SOURCE,
        overrides=overrides,
        supersedes=supersedes,
        created_at=NOW,
    )


def test_assertion_uri_is_stable_and_hierarchical():
    assertion = make_assertion(
        "EA-002",
        scope=Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement Platform",
        ),
    )

    uri = assertion_uri("viking://resources/repo-memory/assertions", assertion)

    assert uri == (
        "viking://resources/repo-memory/assertions/"
        "acme/payments/settlement-platform/_/ea-002.json"
    )


def test_put_writes_json_tags_and_acl():
    client = FakeOpenVikingClient()
    store = OpenVikingAssertionStore(
        client,
        acl_resolver=lambda _: {
            "acl_mode": "restricted",
            "entries": [{"principal": "group:payments", "level": "read"}],
        },
    )
    assertion = make_assertion(
        "EA-002",
        scope=Scope(organization="Acme", domain="Payments"),
        importance="critical",
    )

    uri = store.put(assertion)
    stored = json.loads(client.files[uri])

    assert stored["id"] == "EA-002"
    assert "organization=acme" in client.options[uri]["tags"]
    assert client.options[uri]["acl"]["acl_mode"] == "restricted"


def test_tags_are_deterministic():
    assertion = make_assertion(
        "EA-006",
        type="incident-derived-constraint",
        scope=Scope(
            organization="Acme",
            domain="Payments",
            repository="payment-worker",
        ),
        importance="critical",
    )

    assert assertion_tags(assertion) == [
        "assertion_id=EA-006",
        "type=incident-derived-constraint",
        "status=approved",
        "importance=critical",
        "organization=acme",
        "domain=payments",
        "repository=payment-worker",
    ]


def test_resolve_applies_core_policy_after_loading_openviking_candidates():
    client = FakeOpenVikingClient()
    store = OpenVikingAssertionStore(client)

    policy = make_assertion(
        "EA-001",
        type="policy",
        scope=Scope(organization="Acme"),
    )
    exception = make_assertion(
        "EA-003",
        type="approved-exception",
        scope=Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement",
            repository="legacy-settlement",
        ),
        overrides=("EA-001",),
    )

    store.put(policy)
    store.put(exception)

    result = store.resolve(
        ResolutionContext(
            scope=Scope(
                organization="Acme",
                domain="Payments",
                system="Settlement",
                repository="legacy-settlement",
            ),
            when=NOW,
        )
    )

    assert [item.id for item in result.active] == ["EA-003"]


def test_denied_openviking_entry_is_not_read_or_resolved():
    client = FakeOpenVikingClient()
    store = OpenVikingAssertionStore(client)

    visible = make_assertion(
        "EA-visible",
        scope=Scope(organization="Acme", domain="Payments"),
    )
    hidden = make_assertion(
        "EA-hidden",
        scope=Scope(organization="Acme", domain="Payments"),
    )

    store.put(visible)
    hidden_uri = store.put(hidden)
    client.denied.add(hidden_uri)

    result = store.resolve(
        ResolutionContext(
            scope=Scope(
                organization="Acme",
                domain="Payments",
                repository="payment-api",
            ),
            when=NOW,
        )
    )

    assert [item.id for item in result.active] == ["EA-visible"]
