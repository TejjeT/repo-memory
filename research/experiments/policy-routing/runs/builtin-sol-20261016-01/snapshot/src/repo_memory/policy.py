"""Deterministic applicability and precedence rules.

The policy engine intentionally does not call an LLM. It computes the active
assertion set from authorization, hierarchy, lifecycle, explicit targeting,
supersession, and explicit overrides.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from .models import EngineeringAssertion, Scope

AuthorizationHook = Callable[[EngineeringAssertion], bool]


@dataclass(frozen=True, slots=True)
class ResolutionContext:
    """Inputs required to resolve active engineering assertions."""

    scope: Scope
    when: datetime


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """Resolved active assertions plus non-fatal conflicts."""

    active: tuple[EngineeringAssertion, ...]
    conflicts: tuple[tuple[str, str], ...]


def resolve_assertions(
    assertions: Iterable[EngineeringAssertion],
    context: ResolutionContext,
    *,
    authorize: AuthorizationHook | None = None,
) -> ResolutionResult:
    """Resolve assertions applicable to a target engineering scope.

    Resolution is deterministic:
    authorization -> lifecycle -> applicability -> supersession -> overrides
    -> conflict reporting -> ordering.
    """

    authorize = authorize or (lambda _: True)

    candidates = [
        assertion
        for assertion in assertions
        if authorize(assertion)
        and assertion.active_at(context.when)
        and _applies(assertion, context.scope)
    ]

    remaining = _remove_superseded(candidates)
    remaining = _apply_explicit_overrides(remaining)

    return ResolutionResult(
        active=tuple(sorted(remaining, key=_sort_key)),
        conflicts=_detect_declared_conflicts(remaining),
    )


def _applies(assertion: EngineeringAssertion, target_scope: Scope) -> bool:
    if assertion.scope.applies_to(target_scope):
        return True

    return (
        assertion.scope.same_organization(target_scope)
        and assertion.explicitly_targets_repository(target_scope.repository)
    )


def _remove_superseded(
    assertions: list[EngineeringAssertion],
) -> list[EngineeringAssertion]:
    by_id = {assertion.id: assertion for assertion in assertions}

    superseded_ids = {
        superseded_id
        for assertion in assertions
        for superseded_id in assertion.supersedes
        if superseded_id in by_id
    }
    superseded_ids.update(
        assertion.id
        for assertion in assertions
        if any(successor in by_id for successor in assertion.superseded_by)
    )

    return [assertion for assertion in assertions if assertion.id not in superseded_ids]


def _apply_explicit_overrides(
    assertions: list[EngineeringAssertion],
) -> list[EngineeringAssertion]:
    """Remove only assertions explicitly overridden by an active exception."""

    by_id = {assertion.id: assertion for assertion in assertions}
    overridden_ids = {
        overridden_id
        for assertion in assertions
        if assertion.type == "approved-exception"
        for overridden_id in assertion.overrides
        if overridden_id in by_id
    }
    return [assertion for assertion in assertions if assertion.id not in overridden_ids]


def _detect_declared_conflicts(
    assertions: list[EngineeringAssertion],
) -> tuple[tuple[str, str], ...]:
    ids = {assertion.id for assertion in assertions}
    pairs: set[tuple[str, str]] = set()

    for assertion in assertions:
        for other in assertion.conflicts_with:
            if other in ids:
                pairs.add(tuple(sorted((assertion.id, other))))

    return tuple(sorted(pairs))


def _sort_key(assertion: EngineeringAssertion) -> tuple[int, int, str]:
    importance_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return (
        -assertion.scope.depth(),
        importance_order.get(assertion.importance, 99),
        assertion.id,
    )
