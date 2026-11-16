"""Governed lifecycle (issue #3): transitions, authorization, history, stores."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from test_openviking_adapter import FakeOpenVikingClient

from repo_memory.adapters.openviking import OpenVikingLifecycleStore
from repo_memory.auth import AuthenticationError, VerifiedSession
from repo_memory.lifecycle import (
    ConcurrentModification,
    InMemoryLifecycleStore,
    LifecycleError,
    LifecycleService,
    ScopeRoleAuthority,
)
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext, resolve_assertions

NOW = datetime(2026, 11, 12, tzinfo=UTC)
ORG = Scope(organization="Acme")
PAYMENTS = Scope(organization="Acme", domain="Payments")
REPO = Scope(organization="Acme", domain="Payments", repository="payment-api")


class Directory:
    grants = {
        "alice": ("adr://",),
        "bob": ("adr://",),
        "carol": ("adr://", "incident://"),
        "dave": ("adr://",),
        "outsider": ("wiki://",),
    }

    def grants_for(self, subject):
        return self.grants[subject]


AUTHORITY = ScopeRoleAuthority(
    grants=(
        ("alice", "proposer", PAYMENTS),
        ("bob", "approver", PAYMENTS),
        ("carol", "approver", ORG),
        ("carol", "proposer", ORG),
        ("outsider", "approver", ORG),
    )
)


def session(subject):
    return VerifiedSession(subject=subject, authenticated_at=NOW, method="test")


def assertion(ident="EA-100", *, uri="adr://payments/0042", scope=REPO, **extra):
    return EngineeringAssertion(
        id=ident,
        type="policy",
        content="Worker owns retries.",
        scope=scope,
        status="approved",  # callers cannot choose this; propose forces "proposed"
        importance="high",
        provenance=(Provenance(type="adr", uri=uri, revision="abc123"),),
        created_at=NOW,
        **extra,
    )


@pytest.fixture(params=["memory", "openviking"])
def store(request):
    if request.param == "memory":
        return InMemoryLifecycleStore()
    return OpenVikingLifecycleStore(FakeOpenVikingClient())


@pytest.fixture
def service(store):
    return LifecycleService(store, Directory(), AUTHORITY, clock=lambda: NOW)


def active_ids(store, scope=REPO):
    result = resolve_assertions(store.assertions(), ResolutionContext(scope=scope, when=NOW))
    return [a.id for a in result.active]


def code(excinfo):
    return excinfo.value.code


# -- propose -> approve / reject -> retrieve ---------------------------------


def test_proposal_is_not_retrievable_until_approved(service, store):
    service.propose(session("alice"), assertion(), "from ADR 42")
    assert store.load("EA-100").assertion.status == "proposed"
    assert active_ids(store) == []

    service.approve(session("bob"), "EA-100", "reviewed in architecture board")
    assert active_ids(store) == ["EA-100"]


def test_rejected_proposal_never_becomes_active(service, store):
    service.propose(session("alice"), assertion(), "from ADR 42")
    service.reject(session("bob"), "EA-100", "duplicates EA-006")
    assert active_ids(store) == []
    with pytest.raises(LifecycleError) as excinfo:
        service.approve(session("bob"), "EA-100", "second thoughts")
    assert code(excinfo) == "conflict"


def test_content_and_provenance_are_never_rewritten(service, store):
    original = assertion()
    service.propose(session("alice"), original, "from ADR 42")
    service.approve(session("bob"), "EA-100", "ok")
    service.expire(session("bob"), "EA-100", "service retired")
    service.archive(session("bob"), "EA-100", "cleanup")
    kept = store.load("EA-100").assertion
    assert replace(kept, status=original.status) == original


# -- authorization -----------------------------------------------------------


def test_missing_session_fails_closed(service):
    with pytest.raises(AuthenticationError):
        service.propose(None, assertion(), "x")


def test_unauthorized_transitions_are_rejected(service, store):
    with pytest.raises(LifecycleError) as excinfo:
        service.propose(session("dave"), assertion(), "no role")
    assert code(excinfo) == "forbidden"

    service.propose(session("alice"), assertion(), "from ADR 42")
    with pytest.raises(LifecycleError) as excinfo:
        service.approve(session("alice"), "EA-100", "proposer has no approver role")
    assert code(excinfo) == "forbidden"
    assert store.load("EA-100").assertion.status == "proposed"


def test_role_does_not_extend_outside_its_scope(service):
    other = Scope(organization="Acme", domain="Identity", repository="login")
    with pytest.raises(LifecycleError) as excinfo:
        service.propose(session("alice"), assertion(scope=other), "wrong domain")
    assert code(excinfo) == "forbidden"


def test_proposer_cannot_approve_own_proposal(service, store):
    service.propose(session("carol"), assertion(), "carol holds both roles")
    with pytest.raises(LifecycleError) as excinfo:
        service.approve(session("carol"), "EA-100", "self approval")
    assert code(excinfo) == "forbidden"

    relaxed = replace(service, allow_self_approval=True)
    relaxed.approve(session("carol"), "EA-100", "explicitly allowed by deployment")
    assert store.load("EA-100").assertion.status == "approved"


def test_unreadable_assertion_is_indistinguishable_from_missing(service):
    service.propose(session("alice"), assertion(), "from ADR 42")
    # "outsider" holds an approver role but cannot read the ADR source.
    with pytest.raises(LifecycleError) as denied:
        service.approve(session("outsider"), "EA-100", "x")
    with pytest.raises(LifecycleError) as missing:
        service.approve(session("outsider"), "EA-999", "x")
    assert code(denied) == code(missing) == "not_found"
    assert str(denied.value) == str(missing.value)
    with pytest.raises(LifecycleError) as excinfo:
        service.history(session("outsider"), "EA-100")
    assert code(excinfo) == "not_found"


def test_proposal_cannot_probe_unreadable_ids_through_links(service, store):
    service.propose(session("carol"), assertion("EA-200", uri="incident://INC-7"), "restricted")
    with pytest.raises(LifecycleError) as hidden:
        service.propose(session("alice"), assertion(supersedes=("EA-200",)), "probe")
    with pytest.raises(LifecycleError) as absent:
        service.propose(session("alice"), assertion(supersedes=("EA-404",)), "probe")
    assert code(hidden) == code(absent) == "not_found"
    assert store.load("EA-100") is None


# -- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        replace(assertion(), provenance=()),
        assertion(scope=Scope(repository="payment-api")),
        assertion(superseded_by=("EA-1",)),
    ],
)
def test_invalid_proposals_are_refused(service, bad):
    with pytest.raises(LifecycleError) as excinfo:
        service.propose(session("carol"), bad, "x")
    assert code(excinfo) == "invalid"


def test_every_decision_needs_a_reason(service):
    with pytest.raises(LifecycleError) as excinfo:
        service.propose(session("alice"), assertion(), "   ")
    assert code(excinfo) == "invalid"


# -- supersession, expiry, archive -------------------------------------------


def test_approving_a_successor_supersedes_its_predecessor_atomically(service, store):
    service.propose(session("alice"), assertion("EA-005"), "gateway retries")
    service.approve(session("bob"), "EA-005", "ok")
    service.propose(session("alice"), assertion("EA-006", supersedes=("EA-005",)), "INC-412")
    assert active_ids(store) == ["EA-005"]  # successor still only proposed

    service.approve(session("bob"), "EA-006", "retries move to the worker")
    old = store.load("EA-005").assertion
    assert (old.status, old.superseded_by) == ("superseded", ("EA-006",))
    assert active_ids(store) == ["EA-006"]
    assert old.content == "Worker owns retries." and old.provenance  # history intact
    assert [e["action"] for e in service.history(session("bob"), "EA-005")] == [
        "propose",
        "approve",
        "supersede",
    ]


def test_explicit_supersede_repairs_a_predecessor_left_approved(service, store):
    for ident in ("EA-010", "EA-011"):
        service.propose(session("alice"), assertion(ident), "x")
        service.approve(session("bob"), ident, "ok")
    service.supersede(session("bob"), "EA-010", "EA-011", "EA-011 replaced it in October")
    assert store.load("EA-010").assertion.superseded_by == ("EA-011",)
    assert store.load("EA-011").assertion.supersedes == ("EA-010",)
    assert active_ids(store) == ["EA-011"]


def test_supersede_requires_an_approved_successor(service):
    service.propose(session("alice"), assertion("EA-010"), "x")
    service.approve(session("bob"), "EA-010", "ok")
    service.propose(session("alice"), assertion("EA-011"), "x")
    with pytest.raises(LifecycleError) as excinfo:
        service.supersede(session("bob"), "EA-010", "EA-011", "too early")
    assert code(excinfo) == "conflict"


def test_expire_and_archive_remove_from_retrieval_but_keep_the_record(service, store):
    service.propose(session("alice"), assertion(), "x")
    service.approve(session("bob"), "EA-100", "ok")
    service.expire(session("bob"), "EA-100", "exception window closed")
    assert active_ids(store) == []
    assert store.load("EA-100").assertion.status == "expired"
    service.archive(session("bob"), "EA-100", "cleanup")
    assert store.load("EA-100").assertion.status == "archived"
    assert len(store.history("EA-100")) == 4


# -- repeated and conflicting attempts ---------------------------------------


def test_repeated_decision_is_reported_not_duplicated(service, store):
    service.propose(session("alice"), assertion(), "x")
    service.approve(session("bob"), "EA-100", "ok")
    with pytest.raises(LifecycleError) as excinfo:
        service.approve(session("carol"), "EA-100", "ok again")
    assert code(excinfo) == "already_done"
    assert len(store.history("EA-100")) == 2


def test_duplicate_proposal_id_is_a_conflict(service):
    service.propose(session("alice"), assertion(), "x")
    with pytest.raises(LifecycleError) as excinfo:
        service.propose(session("carol"), assertion(), "same id")
    assert code(excinfo) == "conflict"


def test_stale_write_is_refused_and_nothing_is_written(store):
    """Two reviewers read the same proposal; the second decision loses."""

    service = LifecycleService(store, Directory(), AUTHORITY, clock=lambda: NOW)
    service.propose(session("alice"), assertion(), "x")
    stale = store.load("EA-100")
    service.reject(session("bob"), "EA-100", "first decision")

    with pytest.raises(ConcurrentModification):
        store.commit([(replace(stale.assertion, status="approved"), stale.version)], [])
    assert store.load("EA-100").assertion.status == "rejected"
    assert len(store.history("EA-100")) == 2


def test_service_reports_concurrent_writes(store):
    class Racing:
        """Store wrapper where another writer always gets in first."""

        def __getattr__(self, name):
            return getattr(store, name)

        def commit(self, writes, events):
            raise ConcurrentModification("EA-100")

    service = LifecycleService(store, Directory(), AUTHORITY, clock=lambda: NOW)
    service.propose(session("alice"), assertion(), "x")
    racing = replace(service, store=Racing())
    with pytest.raises(LifecycleError) as excinfo:
        racing.approve(session("bob"), "EA-100", "ok")
    assert code(excinfo) == "concurrent"


# -- history -----------------------------------------------------------------


def test_history_records_attribution_and_source_revisions(service):
    service.propose(session("alice"), assertion(), "from ADR 42")
    service.approve(session("bob"), "EA-100", "reviewed")
    first, second = service.history(session("bob"), "EA-100")
    assert (first["actor"], first["to_status"], first["reason"]) == (
        "alice",
        "proposed",
        "from ADR 42",
    )
    assert (second["actor"], second["from_status"], second["to_status"]) == (
        "bob",
        "proposed",
        "approved",
    )
    assert second["source_revisions"] == [{"uri": "adr://payments/0042", "revision": "abc123"}]
    assert second["at"] == "2026-11-12T00:00:00Z"


def test_history_is_redacted_for_the_caller(service):
    mixed = replace(
        assertion("EA-300"),
        provenance=(
            Provenance(type="adr", uri="adr://payments/0050", revision="r1"),
            Provenance(type="incident", uri="incident://INC-9", revision="r2"),
        ),
        supersedes=("EA-200",),
    )
    service.propose(session("carol"), assertion("EA-200", uri="incident://INC-7"), "restricted")
    replace(service, allow_self_approval=True).approve(session("carol"), "EA-200", "ok")
    service.propose(session("carol"), mixed, "replaces the restricted rule")
    replace(service, allow_self_approval=True).approve(session("carol"), "EA-300", "ok")

    events = service.history(session("bob"), "EA-300")  # bob cannot read incident://
    approve = events[1]
    assert approve["related_ids"] == []  # EA-200 is unreadable to bob
    assert approve["source_revisions"] == [
        {"uri": "adr://payments/0050", "revision": "r1"},
        {"uri": "redacted", "revision": None},
    ]
    full = service.history(session("carol"), "EA-300")[1]
    assert full["related_ids"] == ["EA-200"]
    assert full["source_revisions"][1] == {"uri": "incident://INC-9", "revision": "r2"}
