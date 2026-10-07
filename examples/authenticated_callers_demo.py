"""Reproducible demo for issue #20: authenticated callers, provider boundary.

Two callers hit the same memory through the authenticated path:

- alice: grants for ``doc://`` and ``incident://`` (sees everything)
- bob:   grants for ``doc://`` only (restricted incident stays hidden)

The evidence provider is *external* (untrusted), so it only ever receives
the redacted candidate view; a recording transport captures exactly what
crossed the boundary for each caller. The demo prints both responses and
the outbound views, then asserts the documented differing results and the
absence of cross-caller leakage.

Run:  python examples/authenticated_callers_demo.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from repo_memory.auth import (
    RecordingTransport,
    VerifiedSession,
    assembler_for_session,
)
from repo_memory.context import (
    ContextRequest,
    Evidence,
    EvidenceProvider,
    ExternalEvidenceProvider,
    describe,
)
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext

NOW = datetime(2026, 10, 7, tzinfo=UTC)

PUBLIC_PROVENANCE = (Provenance(type="document", uri="doc://handbook/deploy"),)
RESTRICTED_PROVENANCE = (
    Provenance(
        type="incident",
        uri="incident://restricted/7",
        revision="rev-9",
        access_policy_ref="incident-access",
    ),
)

DIRECTORY = {
    "alice": ("doc://", "incident://"),
    "bob": ("doc://",),
}


class FakeDirectory:
    """Test-double caller directory: server-side subject -> grants mapping."""

    def __init__(self, grants: dict[str, tuple[str, ...]]) -> None:
        self._grants = grants

    def grants_for(self, subject: str) -> tuple[str, ...]:
        return self._grants[subject]


class FakeExternalProvider(EvidenceProvider):
    """Test-double external provider: records the view it was given."""

    def __init__(self) -> None:
        self.seen_views: list[tuple[EngineeringAssertion, ...]] = []

    def collect(
        self,
        request: ContextRequest,
        candidates: tuple[EngineeringAssertion, ...],
    ) -> tuple[Evidence, ...]:
        self.seen_views.append(candidates)
        # Three items probing the authorization boundaries:
        # 1. authorized source + authorized link -> kept for both callers
        # 2. restricted source + authorized link -> kept only for alice
        # 3. authorized source + restricted link -> kept only for alice
        # A hostile provider cannot expand either caller's authorized set.
        return (
            Evidence(
                uri="doc://handbook/deploy-notes",
                kind="doc",
                snippet="deploy notes",
                relates_to=("EA-PUBLIC",),
                score=0.9,
                provenance=PUBLIC_PROVENANCE,
            ),
            Evidence(
                uri="incident://restricted/7/notes",
                kind="doc",
                snippet="restricted notes",
                relates_to=("EA-PUBLIC",),
                score=0.5,
                provenance=RESTRICTED_PROVENANCE,
            ),
            Evidence(
                uri="doc://handbook/secret-notes",
                kind="doc",
                snippet="secret notes",
                relates_to=("EA-SECRET",),
                score=0.7,
                provenance=PUBLIC_PROVENANCE,
            ),
        )


def make_assertions() -> tuple[EngineeringAssertion, ...]:
    return (
        EngineeringAssertion(
            id="EA-PUBLIC",
            type="constraint",
            content="Deploy only from the release branch.",
            scope=Scope(organization="Acme"),
            status="approved",
            importance="high",
            provenance=PUBLIC_PROVENANCE,
            created_at=NOW,
        ),
        EngineeringAssertion(
            id="EA-SECRET",
            type="incident-derived-constraint",
            content="Freeze deploys during incident INC-7 review.",
            scope=Scope(organization="Acme"),
            status="approved",
            importance="critical",
            provenance=RESTRICTED_PROVENANCE,
            created_at=NOW,
        ),
    )


def make_request() -> ContextRequest:
    return ContextRequest(
        task="plan today's deploy",
        resolution=ResolutionContext(scope=Scope(organization="Acme"), when=NOW),
    )


def run_caller(subject: str) -> dict:
    """Run one authenticated request; return response + boundary recording."""
    directory = FakeDirectory(DIRECTORY)
    session = VerifiedSession(subject=subject, authenticated_at=NOW, method="demo")
    transport = RecordingTransport()
    provider = FakeExternalProvider()
    grants = DIRECTORY[subject]
    assembler = assembler_for_session(
        session,
        directory,
        providers=(
            ExternalEvidenceProvider(
                provider,
                # Same grant check for_caller binds internally; the wrapper
                # needs it up front to redact before the provider sees data.
                authorize_provenance=lambda p: any(
                    p.uri.startswith(g) for g in grants
                ),
                transport=transport,
            ),
        ),
    )
    context = assembler.assemble(make_assertions(), make_request())
    return {
        "subject": subject,
        "response": describe(context),
        "assertions": context.assertions,
        "outbound_views": transport.sent_views,
        "provider_seen": provider.seen_views,
    }


def check_no_leakage(result: dict, forbidden_uris: tuple[str, ...]) -> None:
    """Assert no forbidden URI appears anywhere the caller could observe."""
    observed: list[str] = []
    for assertion in result["assertions"]:
        observed.append(assertion.id)
        observed.append(assertion.content)
        for entry in assertion.provenance:
            observed.append(entry.uri)
            observed.append(entry.revision or "")
            observed.append(entry.access_policy_ref or "")
    for view in result["outbound_views"]:
        for assertion in view:
            for entry in assertion.provenance:
                observed.append(entry.uri)
                observed.append(entry.revision or "")
    text = "\n".join(observed)
    for uri in forbidden_uris:
        assert uri not in text, f"leakage: {uri} visible to {result['subject']}"


def main() -> None:
    alice = run_caller("alice")
    bob = run_caller("bob")

    print("== alice (doc:// + incident://) ==")
    print("assertions:", alice["response"]["assertions"])
    for assertion in alice["assertions"]:
        print(f"  {assertion.id}: provenance uris:",
              [p.uri for p in assertion.provenance])
    print("outbound views sent:", len(alice["outbound_views"]))

    print("== bob (doc:// only) ==")
    print("assertions:", bob["response"]["assertions"])
    for assertion in bob["assertions"]:
        print(f"  {assertion.id}: provenance uris:",
              [p.uri for p in assertion.provenance])
    print("outbound views sent:", len(bob["outbound_views"]))

    # Documented differing results.
    assert alice["response"]["assertions"] == ["EA-SECRET", "EA-PUBLIC"], alice["response"]
    assert bob["response"]["assertions"] == ["EA-PUBLIC"], bob["response"]

    # Bob's restricted provenance is redacted, not exposed.
    (public,) = bob["assertions"]
    assert public.id == "EA-PUBLIC"
    assert [p.uri for p in public.provenance] == ["doc://handbook/deploy"]

    # No cross-caller leakage: the restricted incident URI, revision, and
    # policy reference appear nowhere bob can observe -- not in his
    # response, and not in what the external provider received for him.
    check_no_leakage(
        bob,
        ("incident://restricted/7", "rev-9", "incident-access"),
    )

    # The provider cannot expand either caller's authorized set: alice gets
    # all three items (she holds both grants); bob gets only the doc:// item
    # linked to the public assertion. Restricted source and restricted link
    # are both dropped for bob.
    assert [e["uri"] for e in alice["response"]["evidence"]] == [
        "doc://handbook/deploy-notes",
        "doc://handbook/secret-notes",
        "incident://restricted/7/notes",
    ], alice["response"]
    assert [e["uri"] for e in bob["response"]["evidence"]] == [
        "doc://handbook/deploy-notes"
    ], bob["response"]

    # The external provider never saw unredacted provenance for bob.
    for view in bob["provider_seen"]:
        for assertion in view:
            for entry in assertion.provenance:
                assert entry.uri != "incident://restricted/7"
                assert entry.revision is None

    print("OK: differing results, redacted boundary, no leakage.")


if __name__ == "__main__":
    main()
