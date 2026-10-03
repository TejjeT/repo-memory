"""v0.2 context assembly: trusted memory first, retrieval assist second.

Design rule (``docs/v0-scope.md``): RAG may improve relevance; it must not
determine authority.

Assembly order mirrors the retrieval contract:

1. deterministic candidate set via :func:`resolve_assertions`
   (scope resolution -> authorization -> lifecycle filtering ->
   applicability / overrides / supersession)
2. evidence providers may add supporting material, but only items related to
   the authorized set; orphaned evidence is dropped and a provider can never
   promote evidence into an assertion
3. provenance is attached throughout; the evidence budget is applied last

This module is backend-neutral: it defines protocols, not providers.
Provider implementations (OpenViking search, OpenSearch, pgvector, ...)
belong under ``adapters/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from repo_memory.models import EngineeringAssertion, Provenance
from repo_memory.policy import (
    AuthorizationHook,
    ResolutionContext,
    ResolutionResult,
    resolve_assertions,
)


@dataclass(frozen=True, slots=True)
class Evidence:
    """Supporting material retrieved after the authoritative set is fixed.

    Evidence is never authoritative: it cannot add assertions, change
    precedence, or widen permissions. ``relates_to`` links the item to the
    assertion ids it supports; items unrelated to the authorized set are
    dropped during assembly.
    """

    uri: str
    kind: str  # e.g. "adr", "doc", "code"
    snippet: str
    relates_to: tuple[str, ...] = ()
    score: float | None = None
    provenance: tuple[Provenance, ...] = ()


@dataclass(frozen=True, slots=True)
class RepositoryMetadata:
    """Deterministic repository facts supplied by the caller."""

    name: str
    language: str | None = None
    build_tool: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContextRequest:
    """Everything the assembler needs for one engineering task."""

    task: str
    resolution: ResolutionContext
    repository: RepositoryMetadata | None = None
    evidence_budget: int = 10


@dataclass(frozen=True, slots=True)
class AssembledContext:
    """The deterministic core plus bounded retrieval assist."""

    assertions: tuple[EngineeringAssertion, ...]
    evidence: tuple[Evidence, ...]
    repository: RepositoryMetadata | None
    conflicts: tuple[tuple[str, str], ...] = ()
    assembled_at: datetime | None = None


class EvidenceProvider(Protocol):
    """Retrieval-assist source: ranks and surfaces supporting material.

    Implementations must respect the caller's permissions; the assembler
    additionally drops any evidence unrelated to the authorized assertion
    set, so a provider can never expand authority.
    """

    def collect(self, request: ContextRequest) -> tuple[Evidence, ...]:
        """Return candidate supporting evidence for the request."""
        ...


@dataclass(frozen=True, slots=True)
class ContextAssembler:
    """Combine trusted engineering memory with bounded retrieval assist."""

    providers: tuple[EvidenceProvider, ...] = ()
    authorize: AuthorizationHook | None = None

    def assemble(
        self,
        assertions: tuple[EngineeringAssertion, ...],
        request: ContextRequest,
    ) -> AssembledContext:
        """Assemble context: authority first, evidence second."""
        result: ResolutionResult = resolve_assertions(
            assertions,
            request.resolution,
            authorize=self.authorize,
        )
        authorized_ids = {assertion.id for assertion in result.active}

        evidence: list[Evidence] = []
        for provider in self.providers:
            for item in provider.collect(request):
                # Authority boundary: evidence must support the authorized
                # set. Orphaned items are dropped, never promoted.
                if authorized_ids.intersection(item.relates_to):
                    evidence.append(item)

        # Ranking is allowed here: it affects relevance, not authority.
        evidence.sort(
            key=lambda item: item.score if item.score is not None else 0.0,
            reverse=True,
        )
        evidence = evidence[: max(request.evidence_budget, 0)]

        return AssembledContext(
            assertions=result.active,
            evidence=tuple(evidence),
            repository=request.repository,
            conflicts=result.conflicts,
        )


def describe(context: AssembledContext) -> dict[str, Any]:
    """Return a plain-data summary of an assembled context."""
    return {
        "assertions": [a.id for a in context.assertions],
        "evidence": [
            {"uri": e.uri, "kind": e.kind, "relates_to": list(e.relates_to)}
            for e in context.evidence
        ],
        "repository": context.repository.name if context.repository else None,
        "conflicts": [list(c) for c in context.conflicts],
    }
