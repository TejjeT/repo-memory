from datetime import datetime, timezone

from repo_memory.models import EngineeringAssertion, Provenance, Scope, Target
from repo_memory.policy import ResolutionContext, resolve_assertions

NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
SOURCE = (Provenance(type="document", uri="test://source"),)


def assertion(
    assertion_id: str,
    *,
    type: str = "constraint",
    scope: Scope,
    status: str = "approved",
    importance: str = "high",
    applies_to: tuple[Target, ...] = (),
    supersedes: tuple[str, ...] = (),
    superseded_by: tuple[str, ...] = (),
    conflicts_with: tuple[str, ...] = (),
) -> EngineeringAssertion:
    return EngineeringAssertion(
        id=assertion_id,
        type=type,
        content=assertion_id,
        scope=scope,
        applies_to=applies_to,
        status=status,
        importance=importance,
        provenance=SOURCE,
        supersedes=supersedes,
        superseded_by=superseded_by,
        conflicts_with=conflicts_with,
        created_at=NOW,
    )


def test_parent_scope_applies_to_repository():
    item = assertion("EA-001", scope=Scope(organization="Acme", domain="Payments"))
    context = ResolutionContext(
        scope=Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement",
            repository="payment-worker",
        ),
        when=NOW,
    )

    result = resolve_assertions([item], context)

    assert [a.id for a in result.active] == ["EA-001"]


def test_explicit_repository_target_applies_from_broader_scope():
    item = assertion(
        "EA-002",
        scope=Scope(organization="Acme", domain="Payments", system="Settlement"),
        applies_to=(Target(kind="repository", id="payment-worker"),),
    )
    context = ResolutionContext(
        scope=Scope(
            organization="Acme",
            domain="OtherDomain",
            system="OtherSystem",
            repository="payment-worker",
        ),
        when=NOW,
    )

    result = resolve_assertions([item], context)

    assert [a.id for a in result.active] == ["EA-002"]


def test_superseded_assertion_is_not_active():
    old = assertion(
        "EA-005",
        scope=Scope(organization="Acme", domain="Payments", system="Settlement"),
        superseded_by=("EA-006",),
    )
    current = assertion(
        "EA-006",
        scope=Scope(organization="Acme", domain="Payments", system="Settlement"),
        supersedes=("EA-005",),
    )
    context = ResolutionContext(
        scope=Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement",
            repository="payment-api",
        ),
        when=NOW,
    )

    result = resolve_assertions([old, current], context)

    assert [a.id for a in result.active] == ["EA-006"]


def test_narrower_approved_exception_shadows_broader_policy():
    policy = assertion(
        "EA-001",
        type="policy",
        scope=Scope(organization="Acme"),
    )
    exception = assertion(
        "EA-003",
        type="approved-exception",
        scope=Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement",
            repository="legacy-settlement",
        ),
    )
    context = ResolutionContext(
        scope=Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement",
            repository="legacy-settlement",
        ),
        when=NOW,
    )

    result = resolve_assertions([policy, exception], context)

    assert [a.id for a in result.active] == ["EA-003"]


def test_authorization_happens_before_candidate_resolution():
    visible = assertion(
        "EA-visible",
        scope=Scope(organization="Acme", domain="Payments"),
    )
    hidden = assertion(
        "EA-hidden",
        scope=Scope(organization="Acme", domain="Payments"),
    )
    context = ResolutionContext(
        scope=Scope(
            organization="Acme",
            domain="Payments",
            repository="payment-api",
        ),
        when=NOW,
    )

    result = resolve_assertions(
        [visible, hidden],
        context,
        authorize=lambda item: item.id != "EA-hidden",
    )

    assert [a.id for a in result.active] == ["EA-visible"]


def test_declared_conflicts_are_reported_not_silently_resolved():
    first = assertion(
        "EA-100",
        scope=Scope(organization="Acme", domain="Payments"),
        conflicts_with=("EA-101",),
    )
    second = assertion(
        "EA-101",
        scope=Scope(organization="Acme", domain="Payments"),
    )
    context = ResolutionContext(
        scope=Scope(organization="Acme", domain="Payments"),
        when=NOW,
    )

    result = resolve_assertions([first, second], context)

    assert result.conflicts == (("EA-100", "EA-101"),)
    assert {a.id for a in result.active} == {"EA-100", "EA-101"}
