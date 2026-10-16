"""Issue #28: relationship IDs must be safe before external provider calls."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from repo_memory.auth import RecordingTransport, VerifiedSession
from repo_memory.context import ContextAssembler, ContextRequest
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext
from repo_memory.tools import memory_search

NOW = datetime(2026, 10, 16, tzinfo=UTC)
SCOPE = Scope(organization="Acme", repository="billing-api")
LINK_FIELDS = ("overrides", "supersedes", "superseded_by", "conflicts_with")
PUBLIC_SOURCE = Provenance(type="document", uri="doc://handbook")
SECRET_SOURCE = Provenance(type="incident", uri="incident://restricted/7")


class Directory:
    def grants_for(self, subject):
        return {"alice": ("doc://", "incident://"), "bob": ("doc://",)}[subject]


class RecordingProvider:
    def __init__(self):
        self.seen = []

    def collect(self, request, candidates):
        self.seen.append(candidates)
        return ()


def linked_corpus(field):
    public = EngineeringAssertion(
        id="EA-PUBLIC", type="constraint", content="Approved public rule",
        scope=Scope(organization="Acme"), status="approved", importance="high",
        provenance=(PUBLIC_SOURCE, SECRET_SOURCE), created_at=NOW,
        rationale="Restricted incident background",
        **{field: ("EA-SECRET", "EA-MISSING", "EA-OLD", "EA-OTHER")},
    )
    # These targets remain readable independently of search eligibility.
    target = replace(public, **{field: ()}, rationale=None)
    return (
        public,
        replace(target, id="EA-SECRET", status="superseded", provenance=(SECRET_SOURCE,)),
        replace(target, id="EA-OLD", status="superseded", provenance=(PUBLIC_SOURCE,)),
        replace(
            target, id="EA-OTHER", provenance=(PUBLIC_SOURCE,),
            scope=Scope(organization="Acme", repository="other-repo"),
        ),
    )


@pytest.mark.parametrize("field", LINK_FIELDS)
def test_authenticated_search_filters_links_before_provider_and_audit(field):
    corpus = linked_corpus(field)
    external = RecordingProvider()
    trusted = RecordingProvider()

    # Reuse providers across callers so earlier broad grants cannot leak.
    for subject in ("alice", "bob", "alice"):
        session = VerifiedSession(subject, NOW, method="test")
        audit = RecordingTransport()
        result = memory_search(
            session, Directory(), corpus, "plan deploy", SCOPE, when=NOW,
            providers=(trusted,), external_providers=(external,), boundary_transport=audit,
        )
        baseline = memory_search(session, Directory(), corpus, "plan deploy", SCOPE, when=NOW)
        assert result == baseline
        assert [a["id"] for a in result["assertions"]] == ["EA-PUBLIC"]

        expected = ("EA-OLD", "EA-OTHER")
        if subject == "alice":
            expected = ("EA-SECRET", *expected)
        (view,) = audit.sent_views
        assert external.seen[-1] is view
        assert [a.id for a in view] == ["EA-PUBLIC"]
        assert getattr(view[0], field) == expected
        assert result["assertions"][0][field] == list(expected)
        assert "EA-MISSING" not in repr(view)
        if subject == "bob":
            assert "EA-SECRET" not in repr(view)
            assert "incident://restricted/7" not in repr(view)
            assert view[0].rationale is None
        else:
            assert SECRET_SOURCE in view[0].provenance
            assert view[0].rationale == corpus[0].rationale

        # Sanitization must not mutate the corpus or trusted-provider view.
        assert trusted.seen[-1] == (corpus[0],)
        assert trusted.seen[-1][0] is corpus[0]
        assert "EA-MISSING" in getattr(corpus[0], field)
        assert SECRET_SOURCE in trusted.seen[-1][0].provenance


@pytest.mark.parametrize("field", LINK_FIELDS)
def test_external_view_without_assertion_hook_still_drops_unknown_links(field):
    provider = RecordingProvider()
    audit = RecordingTransport()
    assembler = ContextAssembler(
        external_providers=(provider,), authorize_provenance=lambda _: True,
        boundary_transport=audit,
    )
    assembler.assemble(
        linked_corpus(field),
        ContextRequest(task="plan deploy", resolution=ResolutionContext(SCOPE, NOW)),
    )
    (view,) = audit.sent_views
    assert provider.seen[0] is view
    assert getattr(view[0], field) == ("EA-SECRET", "EA-OLD", "EA-OTHER")


def test_external_projection_preserves_override_and_supersession_resolution():
    base = linked_corpus("conflicts_with")[0]
    policy = replace(base, id="EA-POLICY", conflicts_with=(), provenance=(PUBLIC_SOURCE,))
    exception = replace(
        policy, id="EA-EXCEPTION", type="approved-exception", scope=SCOPE,
        overrides=("EA-POLICY",),
    )
    old = replace(policy, id="EA-OLD")
    current = replace(policy, id="EA-CURRENT", supersedes=("EA-OLD",))
    provider = RecordingProvider()
    assembler = ContextAssembler(
        external_providers=(provider,), authorize=lambda _: True,
        authorize_provenance=lambda _: True,
    )
    context = assembler.assemble(
        (policy, exception, old, current),
        ContextRequest(task="plan deploy", resolution=ResolutionContext(SCOPE, NOW)),
    )
    assert [a.id for a in context.assertions] == ["EA-EXCEPTION", "EA-CURRENT"]
    assert provider.seen[0] == context.assertions
    assert provider.seen[0][0].overrides == ("EA-POLICY",)
    assert provider.seen[0][1].supersedes == ("EA-OLD",)
