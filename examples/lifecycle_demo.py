"""Governed lifecycle demo (issue #3). Runs offline with the in-memory store.

    python examples/lifecycle_demo.py

Shows: propose -> approve -> retrieve, an unauthorized attempt, supersession
by an approved successor, expiry, and the caller-safe history.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repo_memory.auth import VerifiedSession  # noqa: E402
from repo_memory.lifecycle import (  # noqa: E402
    InMemoryLifecycleStore,
    LifecycleError,
    LifecycleService,
    ScopeRoleAuthority,
)
from repo_memory.models import EngineeringAssertion, Provenance, Scope  # noqa: E402
from repo_memory.policy import ResolutionContext, resolve_assertions  # noqa: E402

NOW = datetime(2026, 11, 12, tzinfo=UTC)
SETTLEMENT = Scope(organization="Acme", domain="Payments", system="Settlement Platform")
WORKER = Scope(
    organization="Acme", domain="Payments", system="Settlement Platform",
    repository="payment-worker",
)


class Directory:
    """Demo identity source: who may read which evidence."""

    def grants_for(self, subject: str) -> tuple[str, ...]:
        return {"engineer": ("adr://",), "architect": ("adr://", "incident://")}[subject]


def session(subject: str) -> VerifiedSession:
    return VerifiedSession(subject=subject, authenticated_at=NOW, method="demo")


def rule(ident: str, content: str, source: Provenance, **extra) -> EngineeringAssertion:
    return EngineeringAssertion(
        id=ident, type="policy", content=content, scope=SETTLEMENT, status="proposed",
        importance="high", provenance=(source,), created_at=NOW, **extra,
    )


def main() -> None:
    store = InMemoryLifecycleStore()
    service = LifecycleService(
        store,
        Directory(),
        ScopeRoleAuthority(
            grants=(
                ("engineer", "proposer", SETTLEMENT),
                ("architect", "proposer", SETTLEMENT),
                ("architect", "approver", SETTLEMENT),
            )
        ),
        clock=lambda: NOW,
    )

    def active() -> list[str]:
        context = ResolutionContext(scope=WORKER, when=NOW)
        return [a.id for a in resolve_assertions(store.assertions(), context).active]

    old = rule(
        "EA-005", "Gateway retries failed settlement calls three times.",
        Provenance(type="adr", uri="adr://settlement/0031", revision="4f2a9c1"),
    )
    service.propose(session("engineer"), old, "Recorded from ADR 31")
    print("after propose      active:", active())

    try:
        service.approve(session("engineer"), "EA-005", "looks fine to me")
    except LifecycleError as error:
        print(f"engineer approve   refused: {error.code} ({error})")

    service.approve(session("architect"), "EA-005", "Accepted at architecture review")
    print("after approve      active:", active())

    new = rule(
        "EA-006", "The worker owns retries; the gateway does not retry.",
        Provenance(type="incident", uri="incident://INC-412", revision="postmortem-v2"),
        supersedes=("EA-005",),
    )
    service.propose(session("architect"), new, "Duplicate settlement in INC-412")
    print("successor proposed active:", active())
    # The demo deployment has one architect, so self-approval is switched on
    # explicitly. The default refuses it.
    LifecycleService(
        store, service.directory, service.authority, clock=service.clock,
        allow_self_approval=True,
    ).approve(session("architect"), "EA-006", "Approved after incident review")
    print("successor approved active:", active())
    print("EA-005 is now      :", store.load("EA-005").assertion.status)

    print("\nhistory of EA-006 as the engineer (incident source is restricted):")
    try:
        service.history(session("engineer"), "EA-006")
    except LifecycleError as error:
        print(f"  refused: {error.code}")
    print("\nhistory of EA-005 as the engineer:")
    print(json.dumps(service.history(session("engineer"), "EA-005"), indent=2))


if __name__ == "__main__":
    main()
