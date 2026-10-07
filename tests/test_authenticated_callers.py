"""Tests for issue #20: authenticated callers and provider boundary.

Identity and permissions come only from server-side inputs
(:class:`VerifiedSession` + :class:`CallerDirectory`). Client-supplied ids
and grants are validated and rejected when they would widen access; missing
or invalid credentials fail closed. External providers receive only the
redacted candidate view, and two callers produce differing results with no
cross-caller leakage.
"""

from datetime import UTC, datetime

import pytest

from repo_memory.auth import (
    AuthenticationError,
    AuthorizationError,
    RecordingTransport,
    VerifiedSession,
    authenticate,
    resolve_caller,
)
from repo_memory.context import (
    REDACTED_URI,
    Caller,
    ContextAssembler,
    ContextRequest,
    Evidence,
    EvidenceProvider,
    redact_assertion,
    redacted_candidate_view,
)
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext

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
    """Test-double server-side directory: subject -> grants."""

    def __init__(self, grants: dict[str, tuple[str, ...]]) -> None:
        self._grants = grants

    def grants_for(self, subject: str) -> tuple[str, ...]:
        return self._grants[subject]


def make_session(subject: str = "alice") -> VerifiedSession:
    return VerifiedSession(subject=subject, authenticated_at=NOW, method="test")


def make_assertion(
    assertion_id: str,
    provenance: tuple[Provenance, ...] = PUBLIC_SOURCE,
    rationale: str | None = None,
) -> EngineeringAssertion:
    return EngineeringAssertion(
        id=assertion_id,
        type="constraint",
        content=f"content of {assertion_id}",
        scope=Scope(organization="Acme"),
        status="approved",
        importance="high",
        provenance=provenance,
        created_at=NOW,
        rationale=rationale,
    )


def make_request() -> ContextRequest:
    return ContextRequest(
        task="plan deploy",
        resolution=ResolutionContext(scope=Scope(organization="Acme"), when=NOW),
    )


# --- identity: missing/invalid credentials fail closed ---


def test_missing_session_fails_closed():
    directory = FakeDirectory({"alice": ("doc://",)})
    with pytest.raises(AuthenticationError):
        resolve_caller(None, directory)


def test_empty_subject_fails_closed():
    directory = FakeDirectory({"alice": ("doc://",)})
    with pytest.raises(AuthenticationError):
        resolve_caller(VerifiedSession(subject="", authenticated_at=NOW), directory)


def test_unknown_subject_fails_closed_without_leaking_existence():
    directory = FakeDirectory({"alice": ("doc://",)})
    with pytest.raises(AuthenticationError):
        resolve_caller(make_session("mallory"), directory)


def test_grants_come_from_directory_not_client():
    directory = FakeDirectory({"alice": ("doc://",)})
    # A widening claim is rejected outright; the caller is never built
    # from client-supplied grants.
    with pytest.raises(AuthorizationError):
        authenticate(
            make_session("alice"),
            directory,
            claimed_grants=("doc://", "incident://"),
        )
    # Without the widening claim, the caller carries directory grants.
    caller = authenticate(make_session("alice"), directory)
    assert caller == Caller(id="alice", grants=("doc://",))


# --- widening attempts are rejected ---


def test_claimed_caller_id_mismatch_rejected():
    directory = FakeDirectory({"alice": ("doc://",), "bob": ("doc://",)})
    with pytest.raises(AuthorizationError):
        authenticate(
            make_session("alice"), directory, claimed_caller_id="bob"
        )


def test_claimed_caller_id_match_accepted():
    directory = FakeDirectory({"alice": ("doc://",)})
    caller = authenticate(
        make_session("alice"), directory, claimed_caller_id="alice"
    )
    assert caller.id == "alice"


def test_claimed_grant_widening_rejected():
    directory = FakeDirectory({"bob": ("doc://",)})
    with pytest.raises(AuthorizationError):
        authenticate(
            make_session("bob"),
            directory,
            claimed_grants=("doc://", "incident://"),
        )


def test_claimed_grant_subset_accepted_but_not_applied():
    directory = FakeDirectory({"alice": ("doc://", "incident://")})
    caller = authenticate(
        make_session("alice"), directory, claimed_grants=("doc://",)
    )
    # Claims are validated, never applied: the caller keeps directory grants.
    assert caller.grants == ("doc://", "incident://")


# --- external provider boundary: redaction before collect ---


def test_redacted_candidate_view_preserves_authority_redacts_details():
    candidates = (
        make_assertion("EA-1", RESTRICTED_SOURCE),
        make_assertion("EA-2", PUBLIC_SOURCE),
    )
    view = redacted_candidate_view(
        candidates, lambda p: p.uri.startswith("doc://")
    )
    assert [a.id for a in view] == ["EA-1", "EA-2"]
    (redacted,) = view[0].provenance
    assert redacted.uri == REDACTED_URI
    assert redacted.revision is None
    assert redacted.access_policy_ref is None
    assert redacted.type == "incident"
    assert view[1].provenance == PUBLIC_SOURCE


def test_external_providers_require_provenance_hook():
    assembler = ContextAssembler(external_providers=(_StubProvider(()),))
    with pytest.raises(TypeError):
        assembler.assemble((make_assertion("EA-1"),), make_request())


class _StubProvider(EvidenceProvider):
    def __init__(self, items: tuple[Evidence, ...]) -> None:
        self.items = items
        self.seen: list[tuple[EngineeringAssertion, ...]] = []

    def collect(self, request, candidates):
        self.seen.append(candidates)
        return self.items


def test_external_provider_receives_redacted_view_and_sees_no_secrets():
    stub = _StubProvider(())
    transport = RecordingTransport()
    assembler = ContextAssembler.for_caller(
        Caller(id="bob", grants=("doc://",)),
        external_providers=(stub,),
        boundary_transport=transport,
    )
    # Mixed provenance: readable (doc://) but the incident entry is withheld.
    candidates = (
        make_assertion(
            "EA-1", PUBLIC_SOURCE + RESTRICTED_SOURCE, rationale="per incident 7"
        ),
    )
    context = assembler.assemble(candidates, make_request())

    assert len(transport.sent_views) == 1
    (view,) = transport.sent_views
    uris = [entry.uri for entry in view[0].provenance]
    assert uris == ["doc://handbook", REDACTED_URI]
    text = repr(view)
    assert "incident://restricted/7" not in text
    assert "rev-9" not in text
    # The provider saw the same redacted view the transport recorded.
    assert stub.seen[0] == view
    # The response redacts the incident entry and withholds the rationale.
    (assertion,) = context.assertions
    assert [p.uri for p in assertion.provenance] == ["doc://handbook", REDACTED_URI]
    assert assertion.rationale is None


def test_rationale_survives_when_all_provenance_is_readable():
    assembler = ContextAssembler.for_caller(
        Caller(id="alice", grants=("doc://", "incident://"))
    )
    context = assembler.assemble(
        (
            make_assertion(
                "EA-1",
                PUBLIC_SOURCE + RESTRICTED_SOURCE,
                rationale="per handbook and incident 7",
            ),
        ),
        make_request(),
    )
    (assertion,) = context.assertions
    assert [p.uri for p in assertion.provenance] == [
        "doc://handbook",
        "incident://restricted/7",
    ]
    assert assertion.rationale == "per handbook and incident 7"


def test_redact_assertion_without_hook_preserves_all():
    assertion = make_assertion("EA-1", RESTRICTED_SOURCE, rationale="r")
    assert redact_assertion(assertion, None) is assertion


def test_provider_output_cannot_expand_authorized_set():
    """A hostile provider returns evidence for denied assertions and denied
    sources; the assembler drops all of it."""
    provider = _StubProvider(
        (
            Evidence(
                uri="incident://restricted/7/notes",
                kind="doc",
                snippet="x",
                relates_to=("EA-DENIED",),
                provenance=RESTRICTED_SOURCE,
            ),
            Evidence(
                uri="doc://handbook/notes",
                kind="doc",
                snippet="y",
                relates_to=("EA-DENIED",),
                provenance=PUBLIC_SOURCE,
            ),
        )
    )
    caller = Caller(id="bob", grants=("doc://",))
    assembler = ContextAssembler.for_caller(caller, providers=(provider,))
    context = assembler.assemble(
        (make_assertion("EA-DENIED", RESTRICTED_SOURCE),), make_request()
    )
    assert context.assertions == ()
    assert context.evidence == ()


# --- two callers: differing results, no cross-caller leakage ---


def _two_caller_setup():
    directory = FakeDirectory(
        {"alice": ("doc://", "incident://"), "bob": ("doc://",)}
    )
    assertions = (
        make_assertion("EA-PUBLIC", PUBLIC_SOURCE),
        make_assertion("EA-SECRET", RESTRICTED_SOURCE),
    )
    return directory, assertions


def _assemble_for(subject: str, directory, assertions, transport, provider=None):
    session = make_session(subject)
    assembler = ContextAssembler.for_caller(
        authenticate(session, directory),
        external_providers=(provider if provider is not None else _StubProvider(()),),
        boundary_transport=transport,
    )
    return assembler.assemble(assertions, make_request())


def test_shared_provider_is_redacted_per_request_caller():
    """The same provider object serving alice then bob is redacted with each
    request's own hook -- alice's permissions cannot leak into bob's path."""
    directory, assertions = _two_caller_setup()
    provider = _StubProvider(())
    alice_transport = RecordingTransport()
    bob_transport = RecordingTransport()

    _assemble_for("alice", directory, assertions, alice_transport, provider)
    _assemble_for("bob", directory, assertions, bob_transport, provider)

    (alice_view,) = alice_transport.sent_views
    (bob_view,) = bob_transport.sent_views
    # Alice's outbound view keeps the incident URI; bob's redacts it.
    assert "incident://restricted/7" in repr(alice_view)
    assert "incident://restricted/7" not in repr(bob_view)
    # The provider observed exactly what each transport recorded.
    assert provider.seen[0] == alice_view
    assert provider.seen[1] == bob_view


def test_two_callers_produce_documented_differing_results():
    directory, assertions = _two_caller_setup()
    alice_ctx = _assemble_for("alice", directory, assertions, RecordingTransport())
    bob_ctx = _assemble_for("bob", directory, assertions, RecordingTransport())

    assert [a.id for a in alice_ctx.assertions] == ["EA-PUBLIC", "EA-SECRET"]
    assert [a.id for a in bob_ctx.assertions] == ["EA-PUBLIC"]


def test_no_cross_caller_leakage_in_responses():
    directory, assertions = _two_caller_setup()
    bob_ctx = _assemble_for("bob", directory, assertions, RecordingTransport())

    observed = []
    for assertion in bob_ctx.assertions:
        observed.append(assertion.content)
        for entry in assertion.provenance:
            observed.extend(
                [entry.uri, entry.revision or "", entry.access_policy_ref or ""]
            )
    text = "\n".join(observed)
    assert "incident://restricted/7" not in text
    assert "rev-9" not in text
    assert "incident-access" not in text


def test_no_cross_caller_leakage_across_provider_boundary():
    directory, assertions = _two_caller_setup()
    transport = RecordingTransport()
    _assemble_for("bob", directory, assertions, transport)

    assert len(transport.sent_views) == 1
    text = repr(transport.sent_views[0])
    assert "incident://restricted/7" not in text
    assert "rev-9" not in text
    assert "incident-access" not in text


def test_broad_scope_request_cannot_widen_grants():
    """Bob asks for an org-wide scope; authorization still gates per source."""
    directory = FakeDirectory({"bob": ("doc://",)})
    caller = authenticate(make_session("bob"), directory)
    assembler = ContextAssembler.for_caller(caller)
    context = assembler.assemble(
        (
            make_assertion("EA-PUBLIC", PUBLIC_SOURCE),
            make_assertion("EA-SECRET", RESTRICTED_SOURCE),
        ),
        ContextRequest(
            task="sweep everything",
            resolution=ResolutionContext(
                scope=Scope(organization="Acme"), when=NOW
            ),
        ),
    )
    assert [a.id for a in context.assertions] == ["EA-PUBLIC"]


def test_source_less_assertion_stays_denied_on_authenticated_path():
    directory = FakeDirectory({"alice": ("doc://", "incident://")})
    caller = authenticate(make_session("alice"), directory)
    assembler = ContextAssembler.for_caller(caller)
    context = assembler.assemble(
        (make_assertion("EA-ORPHAN", ()),), make_request()
    )
    assert context.assertions == ()
