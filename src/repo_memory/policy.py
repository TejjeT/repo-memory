"""Deterministic applicability and precedence rules.

The policy engine intentionally does not call an LLM. It computes the active
assertion set from hierarchy, lifecycle, explicit targeting, and supersession.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

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

    Rules:
    1. Authorization is evaluated before the assertion can enter the candidate set.
    2. Only approved/effective/non-expired assertions are candidates.
    3. Scope ancestors apply to descendants.
    4. Explicit repository applicability can extend a broader assertion to a repo.
    5. Assertions superseded by another active assertion are removed.
    6. Narrower approved-exception assertions take precedence over broader policies.
    7. Equal-specificity incompatible assertions are reported as conflicts, not guessed away.
    """

    authorize = authorize or (lambda _: True)

    candidates = [
        assertion
        for assertion in assertions
        if authorize(assertion)
        and assertion.active_at(context.when)
        and _applies(assertion, context.scope)
    ]

    by_id = {assertion.id: assertion for assertion in candidates}
    superseded_ids = {
        superseded_id
        for assertion in candidates
        for superseded_id in assertion.supersedes
        if superseded_id in by_id
    }
    superseded_ids.update(
        assertion.id
        for assertion in candidates
        if any(successor in by_id for successor in assertion.superseded_by)
    )

    remaining = [a for a in candidates if a.id not in superseded_ids]
    remaining = _apply_exception_precedence(remaining)

    conflicts = _detect_declared_conflicts(remaining)
    ordered = tuple(sorted(remaining, key=_sort_key))

    return ResolutionResult(active=ordered, conflicts=conflicts)


def _applies(assertion: EngineeringAssertion, target_scope: Scope) -> bool:
    if assertion.scope.applies_to(target_scope):
        return True
    return assertion.explicitly_targets_repository(target_scope.repository)


def _apply_exception_precedence(
    assertions: list[EngineeringAssertion],
) -> list[EngineeringAssertion]:
    """Suppress broader policy assertions only when a narrower approved exception exists.

    This is intentionally conservative. Exceptions do not erase unrelated constraints.
    """

    exceptions = [a for a in assertions if a.type == "approved-exception"]
    if not exceptions:
        return assertions

    result: list[EngineeringAssertion] = []
    for assertion in assertions:
        if assertion.type != "policy":
            result.append(assertion)
            continue

        shadowed = any(
            exception.scope.depth() > assertion.scope.depth()
            and assertion.scope.applies_to(exception.scope)
            for exception in exceptions
        )
        if not shadowed:
            result.append(assertion)

    return result


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
