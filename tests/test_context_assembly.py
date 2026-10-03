"""Tests for v0.2 context assembly: authority first, retrieval assist second."""

from datetime import UTC, datetime

from repo_memory.context import (
    AssembledContext,
    ContextAssembler,
    ContextRequest,
    Evidence,
    EvidenceProvider,
    RepositoryMetadata,
    describe,
)
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext

NOW = datetime(2026, 10, 3, tzinfo=UTC)
SOURCE = (Provenance(type="document", uri="test://source"),)


def make_assertion(assertion_id: str, domain: str = "Payments") -> EngineeringAssertion:
    return EngineeringAssertion(
        id=assertion_id,
        type="constraint",
        content=assertion_id,
        scope=Scope(organization="Acme", domain=domain),
        status="approved",
        importance="high",
        provenance=SOURCE,
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

    def collect(self, request: ContextRequest) -> tuple[Evidence, ...]:
        self.calls += 1
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
