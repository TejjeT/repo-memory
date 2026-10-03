"""Regression tests for issue #10 demo queries.

End-to-end through OpenVikingAssertionStore using the real
examples/payments fixtures and an in-memory protocol-compatible client,
so CI does not require a live OpenViking server.

Authorization follows the retrieval contract's discovery/read/read_provenance
levels: a restricted caller may read an approved API-facing conclusion while
inaccessible incident evidence is redacted.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_memory.adapters.openviking import OpenVikingAssertionStore
from repo_memory.loader import load_assertion
from repo_memory.models import EngineeringAssertion, Scope
from repo_memory.policy import ResolutionContext, resolve_assertions

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "engineering-assertion.schema.json"
FIXTURES = ROOT / "examples" / "payments"

NOW = datetime(2026, 10, 3, tzinfo=UTC)


class FakeOpenVikingClient:
    """Protocol-compatible in-memory client with per-entry ACL denial."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.denied: set[str] = set()
        self.reads: list[str] = []

    def write(
        self,
        uri: str,
        content: str,
        mode: str = "replace",
        options: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        self.files[uri] = content
        return {"uri": uri}

    def read(self, uri: str) -> str:
        if uri in self.denied:
            raise PermissionError(f"access denied: {uri}")
        self.reads.append(uri)
        return self.files[uri]

    def ls(
        self,
        uri: str,
        simple: bool = False,
        recursive: bool = False,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        return [
            {
                "uri": path,
                "access": "denied" if path in self.denied else "allow",
            }
            for path in sorted(self.files)
            if path.startswith(uri)
        ]


@dataclass(frozen=True, slots=True)
class DemoUser:
    name: str
    incident_access: bool


@dataclass(frozen=True, slots=True)
class AccessDecision:
    discover: bool
    read: bool
    read_provenance: bool


ALICE = DemoUser("alice", incident_access=True)
BOB = DemoUser("bob", incident_access=False)


def decide_access(user: DemoUser, assertion: EngineeringAssertion) -> AccessDecision:
    """Placeholder source-aligned authorization (issue #10 scope)."""

    restricted_evidence = any(
        provenance.type == "incident" and provenance.access_policy_ref
        for provenance in assertion.provenance
    )
    if not restricted_evidence or user.incident_access:
        return AccessDecision(discover=True, read=True, read_provenance=True)
    return AccessDecision(discover=True, read=True, read_provenance=False)


def redact_provenance(
    assertion: EngineeringAssertion, decision: AccessDecision
) -> list[dict[str, Any]]:
    redacted: list[dict[str, Any]] = []
    for provenance in assertion.provenance:
        if decision.read_provenance or not (
            provenance.type == "incident" and provenance.access_policy_ref
        ):
            redacted.append({"type": provenance.type, "uri": provenance.uri})
        else:
            redacted.append({"type": provenance.type, "redacted": True})
    return redacted


def load_payments_fixtures() -> list[EngineeringAssertion]:
    """Load and schema-validate every payments experiment fixture."""

    return [load_assertion(path, SCHEMA) for path in sorted(FIXTURES.glob("*.json"))]


def make_store(
    *, deny: tuple[str, ...] = ()
) -> tuple[OpenVikingAssertionStore, FakeOpenVikingClient]:
    client = FakeOpenVikingClient()
    store = OpenVikingAssertionStore(client)
    for assertion in load_payments_fixtures():
        store.put(assertion)
    for assertion_id in deny:
        uri = next(
            uri for uri in client.files if uri.endswith(f"/{assertion_id.lower()}.json")
        )
        client.denied.add(uri)
    return store, client


def resolve_for(
    store: OpenVikingAssertionStore, user: DemoUser, scope: Scope
) -> list[EngineeringAssertion]:
    assertions = store.list_for_organization("Acme")
    decisions = {a.id: decide_access(user, a) for a in assertions}
    readable = [a for a in assertions if decisions[a.id].read]
    result = resolve_assertions(
        readable,
        ResolutionContext(scope=scope, when=NOW),
        authorize=lambda a: decisions[a.id].discover,
    )
    return list(result.active)


def repository_scope(repository: str) -> Scope:
    return Scope(
        organization="Acme",
        domain="Payments",
        system="Settlement Platform",
        repository=repository,
    )


def test_all_six_payments_fixtures_validate_and_load():
    assertions = load_payments_fixtures()

    assert sorted(a.id for a in assertions) == [
        "EA-001",
        "EA-002",
        "EA-003",
        "EA-004",
        "EA-005",
        "EA-006",
    ]


def test_q1_payment_worker_retry_returns_ea002_and_ea006():
    store, _ = make_store()

    ids = [a.id for a in resolve_for(store, ALICE, repository_scope("payment-worker"))]

    assert "EA-002" in ids
    assert "EA-006" in ids
    assert "EA-005" not in ids


def test_q2_legacy_settlement_exception_takes_precedence():
    store, _ = make_store()

    ids = [a.id for a in resolve_for(store, ALICE, repository_scope("legacy-settlement"))]

    assert "EA-003" in ids
    assert "EA-001" not in ids


def test_q3_superseded_retry_excluded_but_historically_inspectable():
    store, _ = make_store()

    ids = [a.id for a in resolve_for(store, ALICE, repository_scope("settlement-engine"))]

    assert "EA-006" in ids
    assert "EA-005" not in ids
    assert "EA-005" in [a.id for a in store.list_for_organization("Acme")]


def test_q4_restricted_user_cannot_discover_denied_assertion():
    store, client = make_store(deny=("EA-006",))

    ids = [a.id for a in resolve_for(store, BOB, repository_scope("payment-api"))]

    assert "EA-006" not in ids
    denied_uri = next(iter(client.denied))
    assert denied_uri not in client.reads


def test_q4_restricted_evidence_is_redacted_not_leaked():
    store, _ = make_store()

    active = resolve_for(store, BOB, repository_scope("payment-api"))
    ea002 = next(a for a in active if a.id == "EA-002")

    assert "EA-002" in [a.id for a in active]
    assert any(
        entry.get("redacted") for entry in redact_provenance(ea002, decide_access(BOB, ea002))
    )
    assert not any(
        entry.get("uri", "").startswith("incident://")
        for entry in redact_provenance(ea002, decide_access(BOB, ea002))
    )


def test_provenance_survives_openviking_round_trip():
    store, _ = make_store()

    stored = {a.id: a for a in store.list_for_organization("Acme")}

    assert [p.uri for p in stored["EA-002"].provenance] == [
        "incident://INC-412",
        "github://acme/settlement-engine/docs/adr/0037.md",
    ]
