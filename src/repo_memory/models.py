"""Typed models for engineering assertions.

The models are intentionally lightweight dataclasses so the core contract stays
portable and does not depend on a web framework, ORM, or agent SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Scope:
    """Hierarchical engineering scope.

    Scope values are optional because an assertion may stop at any level.
    """

    organization: str | None = None
    domain: str | None = None
    system: str | None = None
    repository: str | None = None
    component: str | None = None
    branch: str | None = None
    pull_request: str | None = None

    def as_path(self) -> tuple[str, ...]:
        """Return populated scope levels in hierarchy order."""

        return tuple(
            value
            for value in (
                self.organization,
                self.domain,
                self.system,
                self.repository,
                self.component,
                self.branch,
                self.pull_request,
            )
            if value is not None
        )

    def depth(self) -> int:
        """Return the number of populated hierarchical levels."""

        return len(self.as_path())

    def applies_to(self, target: "Scope") -> bool:
        """Return True when this scope is an ancestor/equal of the target scope.

        A populated level must match the target at the same level. Missing levels
        behave like wildcards below the last populated parent.
        """

        for own, other in zip(_scope_values(self), _scope_values(target), strict=True):
            if own is None:
                continue
            if other != own:
                return False
        return True


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
    supersedes: tuple[str, ...] = field(default_factory=tuple)
    superseded_by: tuple[str, ...] = field(default_factory=tuple)
    conflicts_with: tuple[str, ...] = field(default_factory=tuple)

    def active_at(self, when: datetime) -> bool:
        """Return True when lifecycle and effective dates make this assertion active."""

        if self.status != "approved":
            return False
        if self.effective_from is not None and when < self.effective_from:
            return False
        if self.expires_at is not None and when >= self.expires_at:
            return False
        return True

    def explicitly_targets_repository(self, repository: str | None) -> bool:
        """Return True if applies_to explicitly contains the repository."""

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
