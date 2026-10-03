"""Typed models for engineering assertions.

The models are intentionally lightweight dataclasses so the core contract stays
portable and does not depend on a web framework, ORM, or agent SDK.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Scope:
    """Hierarchical engineering scope."""

    organization: str | None = None
    domain: str | None = None
    system: str | None = None
    repository: str | None = None
    component: str | None = None
    branch: str | None = None
    pull_request: str | None = None

    def as_path(self) -> tuple[str, ...]:
        """Return populated scope levels in hierarchy order."""

        return tuple(value for value in _scope_values(self) if value is not None)

    def depth(self) -> int:
        """Return the number of populated hierarchical levels."""

        return len(self.as_path())

    def applies_to(self, target: Scope) -> bool:
        """Return whether this scope is an ancestor/equal of the target."""

        for own, other in zip(_scope_values(self), _scope_values(target), strict=True):
            if own is not None and other != own:
                return False
        return True

    def same_organization(self, target: Scope) -> bool:
        """Return whether explicit targeting stays inside the same organization."""

        if self.organization is None or target.organization is None:
            return False
        return self.organization == target.organization


@dataclass(frozen=True, slots=True)
class Provenance:
    """Source evidence backing an engineering assertion."""

    type: str
    uri: str
    revision: str | None = None
    access_policy_ref: str | None = None
    last_validated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Target:
    """Explicit applicability target."""

    kind: str
    id: str


@dataclass(frozen=True, slots=True)
class EngineeringAssertion:
    """Durable engineering assertion used by the policy engine."""

    id: str
    type: str
    content: str
    scope: Scope
    status: str
    importance: str
    provenance: tuple[Provenance, ...]
    created_at: datetime
    rationale: str | None = None
    applies_to: tuple[Target, ...] = field(default_factory=tuple)
    confidence: float | None = None
    owner: str | None = None
    effective_from: datetime | None = None
    review_after: datetime | None = None
    expires_at: datetime | None = None
    overrides: tuple[str, ...] = field(default_factory=tuple)
    supersedes: tuple[str, ...] = field(default_factory=tuple)
    superseded_by: tuple[str, ...] = field(default_factory=tuple)
    conflicts_with: tuple[str, ...] = field(default_factory=tuple)

    def active_at(self, when: datetime) -> bool:
        """Return whether lifecycle and effective dates make this assertion active."""

        if self.status != "approved":
            return False
        if self.effective_from is not None and when < self.effective_from:
            return False
        return self.expires_at is None or when < self.expires_at

    def explicitly_targets_repository(self, repository: str | None) -> bool:
        """Return whether applies_to explicitly contains the repository."""

        if repository is None:
            return False
        return any(
            target.kind == "repository" and target.id == repository
            for target in self.applies_to
        )


def _scope_values(scope: Scope) -> tuple[str | None, ...]:
    return (
        scope.organization,
        scope.domain,
        scope.system,
        scope.repository,
        scope.component,
        scope.branch,
        scope.pull_request,
    )


def tupleize(values: Iterable[str] | None) -> tuple[str, ...]:
    """Convert optional iterables to stable immutable tuples."""

    return tuple(values or ())
