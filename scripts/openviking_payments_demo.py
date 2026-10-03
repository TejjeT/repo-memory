"""Executable prototype for issue #10: repo-memory policy adapter on OpenViking.

Loads the payments-system experiment fixtures into an OpenViking-backed
assertion store and runs the four demo queries from the issue:

1. payment-worker retry task        -> EA-002 + EA-006 (EA-005 excluded)
2. legacy-settlement runtime task   -> EA-003 active, exception precedence over EA-001
3. gateway retry task               -> EA-006 active, EA-005 historical only
4. restricted user (Bob)            -> cannot retrieve unauthorized assertions/evidence

Uses an in-memory client implementing the adapter's OpenVikingClient protocol,
so it runs without a live OpenViking server. The official SyncHTTPClient
exposes compatible operations; see scripts/openviking_smoke.py for the live
server variant.

Run:  python scripts/openviking_payments_demo.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repo_memory.adapters.openviking import OpenVikingAssertionStore  # noqa: E402
from repo_memory.loader import load_assertion  # noqa: E402
from repo_memory.models import EngineeringAssertion, Scope  # noqa: E402
from repo_memory.policy import ResolutionContext, resolve_assertions  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "engineering-assertion.schema.json"
FIXTURES = ROOT / "examples" / "payments"

# Fixed "now": after EA-006 effective_from (2026-06-12), before EA-003 review.
NOW = datetime(2026, 10, 3, tzinfo=UTC)


class InMemoryVikingClient:
    """Protocol-compatible stand-in for OpenViking's SyncHTTPClient.

    The ``denied`` set simulates OpenViking group ACLs: denied entries are
    filtered at ``ls`` time, so unauthorized callers never learn they exist.
    """

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.denied: set[str] = set()

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
    """Caller in the payments experiment access model."""

    name: str
    teams: tuple[str, ...]
    incident_access: bool


@dataclass(frozen=True, slots=True)
class AccessDecision:
    """Placeholder source-aligned authorization decision (issue #10 scope)."""

    discover: bool
    read: bool
    read_provenance: bool


ALICE = DemoUser("alice", ("payments-platform",), incident_access=True)
BOB = DemoUser("bob", ("external-integrations",), incident_access=False)
CAROL = DemoUser("carol", ("security-platform",), incident_access=True)


def decide_access(user: DemoUser, assertion: EngineeringAssertion) -> AccessDecision:
    """Decide discover/read/read_provenance for one assertion.

    Incident evidence carrying an ``access_policy_ref`` is inspectable only
    by callers with incident access. The approved engineering conclusion may
    still be discoverable and readable with redacted provenance, per the
    retrieval contract's discovery/content/provenance levels.
    """

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
    """Render provenance for a caller, redacting inaccessible evidence."""

    redacted: list[dict[str, Any]] = []
    for provenance in assertion.provenance:
        if decision.read_provenance or not (
            provenance.type == "incident" and provenance.access_policy_ref
        ):
            redacted.append({"type": provenance.type, "uri": provenance.uri})
        else:
            redacted.append({"type": provenance.type, "redacted": True})
    return redacted


def load_fixtures() -> list[EngineeringAssertion]:
    """Load and schema-validate every payments experiment fixture."""

    assertions = [
        load_assertion(path, SCHEMA) for path in sorted(FIXTURES.glob("*.json"))
    ]
    ids = sorted(assertion.id for assertion in assertions)
    assert ids == ["EA-001", "EA-002", "EA-003", "EA-004", "EA-005", "EA-006"], ids
    return assertions


def build_store(
    user: DemoUser, *, deny: tuple[str, ...] = ()
) -> tuple[OpenVikingAssertionStore, InMemoryVikingClient]:
    """Put all fixtures into a per-user store; ``deny`` simulates ACL filtering."""

    client = InMemoryVikingClient()
    store = OpenVikingAssertionStore(client)
    for assertion in load_fixtures():
        store.put(assertion)
    for assertion_id in deny:
        uri = next(
            uri for uri in client.files if uri.endswith(f"/{assertion_id.lower()}.json")
        )
        client.denied.add(uri)
    return store, client


def retrieve(
    store: OpenVikingAssertionStore, user: DemoUser, scope: Scope
) -> dict[str, Any]:
    """Run the retrieval pipeline: ACL filter -> authorization -> policy -> redact."""

    assertions = store.list_for_organization("Acme")
    decisions = {assertion.id: decide_access(user, assertion) for assertion in assertions}
    readable = [
        assertion for assertion in assertions if decisions[assertion.id].read
    ]
    result = resolve_assertions(
        readable,
        ResolutionContext(scope=scope, when=NOW),
        authorize=lambda assertion: decisions[assertion.id].discover,
    )
    return {
        "assertions": [
            {
                "id": assertion.id,
                "content": assertion.content,
                "type": assertion.type,
                "importance": assertion.importance,
                "status": assertion.status,
                "provenance": redact_provenance(assertion, decisions[assertion.id]),
            }
            for assertion in result.active
        ],
        "conflicts": [list(pair) for pair in result.conflicts],
    }


def show(title: str, response: dict[str, Any]) -> None:
    print(f"\n### {title}")
    print(json.dumps(response, indent=2))


def main() -> None:
    # Q1: payment-worker retry task (Alice has full access).
    store, _ = build_store(ALICE)
    response = retrieve(
        store,
        ALICE,
        Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement Platform",
            repository="payment-worker",
        ),
    )
    show("Q1 - payment-worker retry task (alice)", response)
    active = [item["id"] for item in response["assertions"]]
    assert "EA-002" in active, "EA-002 idempotency constraint must be returned"
    assert "EA-006" in active, "EA-006 current retry policy must be returned"
    assert "EA-005" not in active, "EA-005 is superseded and must be excluded"
    print("Q1 PASS: EA-002 + EA-006 active, EA-005 excluded")

    # Q2: legacy-settlement runtime task (Alice). EA-003 overrides EA-001.
    response = retrieve(
        store,
        ALICE,
        Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement Platform",
            repository="legacy-settlement",
        ),
    )
    show("Q2 - legacy-settlement runtime task (alice)", response)
    active = [item["id"] for item in response["assertions"]]
    assert "EA-003" in active, "EA-003 approved exception must be active"
    assert "EA-001" not in active, "EA-001 must be suppressed by EA-003's override"
    print("Q2 PASS: EA-003 active with exception precedence over EA-001")

    # Q3: gateway retry task (Alice). EA-006 active, EA-005 historical only.
    response = retrieve(
        store,
        ALICE,
        Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement Platform",
            repository="settlement-engine",
        ),
    )
    show("Q3 - gateway retry task (alice)", response)
    active = [item["id"] for item in response["assertions"]]
    assert "EA-006" in active, "EA-006 must be the active retry guidance"
    assert "EA-005" not in active, "EA-005 must not appear as current guidance"
    historical = [a.id for a in store.list_for_organization("Acme")]
    assert "EA-005" in historical, "superseded assertions stay inspectable"
    print("Q3 PASS: EA-006 active, EA-005 excluded from normal retrieval")

    # Q4: restricted user (Bob). EA-006 denied at the ACL layer (existence
    # hidden); EA-002's incident evidence redacted, conclusion visible.
    bob_store, bob_client = build_store(BOB, deny=("EA-006",))
    response = retrieve(
        bob_store,
        BOB,
        Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement Platform",
            repository="payment-api",
        ),
    )
    show("Q4 - payment-api task (bob, restricted)", response)
    active = [item["id"] for item in response["assertions"]]
    assert "EA-006" not in active, "Bob must not retrieve the restricted assertion"
    assert "EA-002" in active, "Bob may read the API-facing conclusion"
    ea002 = next(item for item in response["assertions"] if item["id"] == "EA-002")
    assert any(
        entry.get("redacted") for entry in ea002["provenance"]
    ), "Bob must not see restricted incident evidence"
    denied_uri = next(iter(bob_client.denied))
    listed = {
        entry["uri"]: entry
        for entry in bob_client.ls(
            "viking://resources/repo-memory/assertions/acme/", recursive=True
        )
    }
    assert listed[denied_uri]["access"] == "denied", (
        "denied entries must be marked at ls time so the adapter skips them"
    )
    try:
        bob_client.read(denied_uri)
    except PermissionError:
        pass
    else:
        raise AssertionError("denied entries must not be readable")
    print("Q4 PASS: EA-006 undiscoverable to Bob; EA-002 provenance redacted")

    print("\nAll four demo queries passed.")


if __name__ == "__main__":
    main()
