"""Tests for v0.2 context assembly: authority first, retrieval assist second."""

from datetime import UTC, datetime

from repo_memory.context import (
    REDACTED_URI,
    AssembledContext,
    Caller,
    ContextAssembler,
    ContextRequest,
    Evidence,
    EvidenceProvider,
    RepositoryMetadata,
    describe,
    redact_provenance,
)
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext

NOW = datetime(2026, 10, 3, tzinfo=UTC)
SOURCE = (Provenance(type="document", uri="test://source"),)
INCIDENT_SOURCE = (
    Provenance(
        type="incident",
        uri="incident://restricted/42",
        access_policy_ref="incident-access",
    ),
)


def make_assertion(
    assertion_id: str,
    domain: str = "Payments",
    provenance: tuple[Provenance, ...] = SOURCE,
) -> EngineeringAssertion:
    return EngineeringAssertion(
        id=assertion_id,
        type="constraint",
        content=assertion_id,
        scope=Scope(organization="Acme", domain=domain),
        status="approved",
        importance="high",
        provenance=provenance,
        created_at=NOW,
    )


def make_request() -> ContextRequest:
    return ContextRequest(
        task="upgrade Java 17 to 25 in payment-api",
        resolution=ResolutionContext(
            scope=Scope(organization="Acme", domain="Payments", repository="payment-api"),
            when=NOW,
        ),
        repository=RepositoryMetadata(name="payment-api", language="java", build_tool="maven"),
        evidence_budget=10,
    )


class FakeProvider(EvidenceProvider):
    def __init__(self, items: tuple[Evidence, ...]) -> None:
        self.items = items
        self.calls = 0
        self.seen_candidates: tuple[EngineeringAssertion, ...] = ()

    def collect(
        self,
        request: ContextRequest,
        candidates: tuple[EngineeringAssertion, ...],
    ) -> tuple[Evidence, ...]:
        self.calls += 1
        self.seen_candidates = candidates
        return self.items


def make_evidence(uri: str, relates_to: tuple[str, ...], score: float | None = 0.5) -> Evidence:
    return Evidence(
        uri=uri,
        kind="doc",
        snippet=f"snippet for {uri}",
        relates_to=relates_to,
        score=score,
        provenance=SOURCE,
    )


def test_authorized_evidence_is_included_and_ranked():
    provider = FakeProvider(
        (
            make_evidence("doc://low", ("EA-1",), score=0.2),
            make_evidence("doc://high", ("EA-1",), score=0.9),
        )
    )
    assembler = ContextAssembler(providers=(provider,))
    context = assembler.assemble((make_assertion("EA-1"),), make_request())

    assert [a.id for a in context.assertions] == ["EA-1"]
    assert [e.uri for e in context.evidence] == ["doc://high", "doc://low"]
    assert context.repository is not None and context.repository.name == "payment-api"


def test_orphan_evidence_is_dropped_never_promoted():
    provider = FakeProvider(
        (
            make_evidence("doc://orphan", ()),
            make_evidence("doc://other-assertion", ("EA-999",)),
        )
    )
    assembler = ContextAssembler(providers=(provider,))
    context = assembler.assemble((make_assertion("EA-1"),), make_request())

    assert [a.id for a in context.assertions] == ["EA-1"]
    assert context.evidence == ()


def test_evidence_for_denied_assertion_is_dropped():
    provider = FakeProvider((make_evidence("doc://secret", ("EA-006",)),))
    assembler = ContextAssembler(
        providers=(provider,),
        authorize=lambda assertion: assertion.id != "EA-006",
    )
    context = assembler.assemble(
        (make_assertion("EA-1"), make_assertion("EA-006")),
        make_request(),
    )

    assert [a.id for a in context.assertions] == ["EA-1"]
    assert context.evidence == ()


def test_providers_cannot_alter_the_deterministic_set():
    provider = FakeProvider((make_evidence("doc://x", ("EA-1",), score=1.0),))
    plain = ContextAssembler().assemble((make_assertion("EA-1"),), make_request())
    assisted = ContextAssembler(providers=(provider,)).assemble(
        (make_assertion("EA-1"),), make_request()
    )

    assert [a.id for a in plain.assertions] == [a.id for a in assisted.assertions]
    assert isinstance(assisted, AssembledContext)


def test_evidence_budget_is_enforced():
    provider = FakeProvider(
        tuple(make_evidence(f"doc://{i}", ("EA-1",), score=float(i)) for i in range(5))
    )
    request = make_request()
    request = ContextRequest(
        task=request.task,
        resolution=request.resolution,
        repository=request.repository,
        evidence_budget=2,
    )
    context = ContextAssembler(providers=(provider,)).assemble(
        (make_assertion("EA-1"),), request
    )

    assert [e.uri for e in context.evidence] == ["doc://4", "doc://3"]


def test_provenance_preserved_end_to_end():
    provider = FakeProvider((make_evidence("doc://adr", ("EA-1",)),))
    context = ContextAssembler(providers=(provider,)).assemble(
        (make_assertion("EA-1"),), make_request()
    )

    assert context.assertions[0].provenance == SOURCE
    assert context.evidence[0].provenance == SOURCE
    summary = describe(context)
    assert summary["assertions"] == ["EA-1"]
    assert summary["evidence"][0]["uri"] == "doc://adr"


def test_evidence_with_denied_source_is_dropped():
    """Relevance is not authorization: an item linked to an authorized
    assertion is still dropped when its own source is off-limits."""
    provider = FakeProvider(
        (
            make_evidence("doc://public", ("EA-1",)),
            make_evidence("incident://restricted/7", ("EA-1",)),
        )
    )
    assembler = ContextAssembler(
        providers=(provider,),
        authorize_evidence=lambda item: not item.uri.startswith("incident://"),
    )
    context = assembler.assemble((make_assertion("EA-1"),), make_request())

    assert [e.uri for e in context.evidence] == ["doc://public"]


def test_mixed_links_have_denied_ids_stripped():
    """relates_to=(allowed, denied): the item is kept for the allowed link,
    and the denied assertion id is never exposed."""
    provider = FakeProvider((make_evidence("doc://mixed", ("EA-1", "EA-006")),))
    assembler = ContextAssembler(
        providers=(provider,),
        authorize=lambda assertion: assertion.id != "EA-006",
    )
    context = assembler.assemble(
        (make_assertion("EA-1"), make_assertion("EA-006")),
        make_request(),
    )

    assert [a.id for a in context.assertions] == ["EA-1"]
    assert len(context.evidence) == 1
    assert context.evidence[0].relates_to == ("EA-1",)
    assert "EA-006" not in str(describe(context))


def test_providers_receive_only_safe_candidates():
    provider = FakeProvider(())
    assembler = ContextAssembler(
        providers=(provider,),
        authorize=lambda assertion: assertion.id != "EA-006",
    )
    assembler.assemble(
        (make_assertion("EA-1"), make_assertion("EA-006")),
        make_request(),
    )

    assert [a.id for a in provider.seen_candidates] == ["EA-1"]


def test_bob_end_to_end_provenance_redaction():
    """Bob may read EA-002's conclusion but not its incident provenance.

    Mirrors the payments demo Q4: assertion authorization (read) is
    independent from provenance authorization (read_provenance).
    """
    assertion = make_assertion("EA-002", provenance=INCIDENT_SOURCE + SOURCE)
    evidence = Evidence(
        uri="doc://notes",
        kind="doc",
        snippet="notes",
        relates_to=("EA-002",),
        provenance=INCIDENT_SOURCE,
    )
    provider = FakeProvider((evidence,))
    assembler = ContextAssembler(
        providers=(provider,),
        authorize=lambda a: True,  # Bob may read the conclusion
        authorize_provenance=lambda p: p.type != "incident",  # not the source
    )
    context = assembler.assemble((assertion,), make_request())

    assert [a.id for a in context.assertions] == ["EA-002"]
    provenance = context.assertions[0].provenance
    assert len(provenance) == 2
    incident = next(p for p in provenance if p.type == "incident")
    assert incident.uri == REDACTED_URI
    assert incident.access_policy_ref is None
    assert incident.revision is None
    document = next(p for p in provenance if p.type == "document")
    assert document.uri == "test://source"
    assert context.evidence[0].provenance[0].uri == REDACTED_URI


def test_redact_provenance_without_hook_preserves_all():
    assert redact_provenance(SOURCE, None) == SOURCE


def test_for_caller_binds_all_hooks_to_one_identity():
    """Issue #15: one authenticated caller drives assertion, evidence, and
    provenance authorization together."""
    bob = Caller(id="bob", grants=("test://", "doc://"))
    provider = FakeProvider(
        (
            make_evidence("doc://notes", ("EA-001",)),
            make_evidence("incident://restricted/42", ("EA-001",)),
        )
    )
    assembler = ContextAssembler.for_caller(
        bob, providers=(provider,), 
    )
    context = assembler.assemble(
        (make_assertion("EA-001", provenance=INCIDENT_SOURCE + SOURCE),),
        make_request(),
    )
    # Assertion readable via the granted document source; incident evidence
    # dropped; incident provenance redacted.
    assert [a.id for a in context.assertions] == ["EA-001"]
    assert [e.uri for e in context.evidence] == ["doc://notes"]
    incident = next(
        p for p in context.assertions[0].provenance if p.type == "incident"
    )
    assert incident.uri == REDACTED_URI


def test_for_caller_denies_assertion_with_empty_provenance():
    """Regression: a caller with grants must not read an assertion that
    lists no provenance sources -- deny by default means there is nothing
    to authorize against."""
    caller = Caller(id="alice", grants=("test://", "doc://"))
    assembler = ContextAssembler.for_caller(caller)
    context = assembler.assemble(
        (make_assertion("EA-001", provenance=()),), make_request()
    )
    assert context.assertions == ()


def test_for_caller_denies_assertion_with_only_restricted_provenance():
    """A caller with no grant covering any provenance source cannot read the
    assertion at all."""
    bob = Caller(id="bob", grants=("doc://",))
    assembler = ContextAssembler.for_caller(bob)
    context = assembler.assemble(
        (make_assertion("EA-001", provenance=INCIDENT_SOURCE),), make_request()
    )
    assert context.assertions == ()


def test_for_caller_with_no_grants_denies_everything():
    nobody = Caller(id="nobody")
    provider = FakeProvider((make_evidence("doc://notes", ("EA-001",)),))
    assembler = ContextAssembler.for_caller(nobody, providers=(provider,))
    context = assembler.assemble((make_assertion("EA-001"),), make_request())
    assert context.assertions == ()
    assert context.evidence == ()


def test_for_caller_explicit_hooks_win():
    """Explicitly passed hooks override the caller-derived defaults."""
    bob = Caller(id="bob", grants=())
    provider = FakeProvider((make_evidence("doc://notes", ("EA-001",)),))
    assembler = ContextAssembler.for_caller(
        bob,
        providers=(provider,),
        authorize=lambda a: True,
        authorize_evidence=lambda e: True,
        authorize_provenance=lambda p: True,
    )
    context = assembler.assemble(
        (make_assertion("EA-001", provenance=INCIDENT_SOURCE),), make_request()
    )
    assert [a.id for a in context.assertions] == ["EA-001"]
    assert [e.uri for e in context.evidence] == ["doc://notes"]
    assert context.assertions[0].provenance[0].uri == "incident://restricted/42"


def test_caller_may_access_uses_prefix_grants():
    caller = Caller(id="x", grants=("doc://",))
    assert caller.may_access("doc://notes")
    assert not caller.may_access("incident://restricted/42")
    assert not caller.may_access("other-doc://notes")


def test_plain_constructor_keeps_permissive_defaults():
    """Backward compatibility: the plain constructor still defaults to
    permissive behavior when hooks are omitted."""
    provider = FakeProvider((make_evidence("incident://restricted/42", ("EA-001",)),))
    assembler = ContextAssembler(providers=(provider,))
    context = assembler.assemble(
        (make_assertion("EA-001", provenance=INCIDENT_SOURCE),), make_request()
    )
    assert [a.id for a in context.assertions] == ["EA-001"]
    assert [e.uri for e in context.evidence] == ["incident://restricted/42"]
