"""v0.2 context assembly: trusted memory first, retrieval assist second.

Design rule (``docs/v0-scope.md``): RAG may improve relevance; it must not
determine authority.

Assembly order mirrors the retrieval contract:

1. deterministic candidate set via :func:`resolve_assertions`
   (scope resolution -> authorization -> lifecycle filtering ->
   applicability / overrides / supersession)
2. evidence providers receive the resolved safe candidates explicitly and may
   add supporting material, but two boundaries are enforced before any
   ranking or budgeting:

   - relevance is not authorization: links outside the safe set are stripped
     from ``relates_to`` (items left with no safe links are dropped), and an
     optional ``authorize_evidence`` hook enforces caller/source
     authorization on the evidence itself
   - assertion authorization is not provenance authorization: provenance the
     caller may not inspect is redacted (URIs, revisions, and policy
     references withheld) via an optional ``authorize_provenance`` hook

3. provenance is attached throughout; the evidence budget is applied last

This module is backend-neutral: it defines protocols, not providers.
Provider implementations (OpenViking search, OpenSearch, pgvector, ...)
belong under ``adapters/``.

Provider trust boundary: ``EvidenceProvider.collect`` receives the resolved
safe candidates with their *unredacted* provenance, because a provider needs
source details to scope retrieval. Providers are therefore trusted
in-process components. An untrusted or external provider must be wrapped in
an adapter that redacts what it may see *before* ``collect`` runs -- the
assembler never hands untrusted code unredacted provenance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Protocol

from repo_memory.models import EngineeringAssertion, Provenance
from repo_memory.policy import (
    AuthorizationHook,
    ResolutionContext,
    ResolutionResult,
    resolve_assertions,
)

#: Sentinel URI marking a redacted provenance entry. The entry keeps its
#: ``type`` (so the caller knows what kind of evidence existed) while the
#: URI, revision, and policy reference are withheld.
REDACTED_URI = "redacted"

#: Decides whether the caller may inspect one provenance entry's details.
ProvenanceAuthorizationHook = Callable[[Provenance], bool]


@dataclass(frozen=True, slots=True)
class Evidence:
    """Supporting material retrieved after the authoritative set is fixed.

    Evidence is never authoritative: it cannot add assertions, change
    precedence, or widen permissions. ``relates_to`` links the item to the
    assertion ids it supports; links outside the authorized set are stripped
    during assembly, and items left with no safe links are dropped.
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
    """The deterministic core plus bounded, caller-safe retrieval assist."""

    assertions: tuple[EngineeringAssertion, ...]
    evidence: tuple[Evidence, ...]
    repository: RepositoryMetadata | None
    conflicts: tuple[tuple[str, str], ...] = ()
    assembled_at: datetime | None = None


#: Decides whether the caller may inspect one evidence item's source.
#: Relevance is not authorization: a provider item linked to an authorized
#: assertion is still dropped when its own source is off-limits.
EvidenceAuthorizationHook = Callable[[Evidence], bool]


@dataclass(frozen=True, slots=True)
class Caller:
    """Authenticated caller identity for authorization decisions.

    The core contract does not define an identity provider (see
    ``docs/retrieval-contract.md`` §1): adapters resolve their own callers
    (a user, team, OIDC subject, service account) into this shape.
    ``grants`` are permitted source URI prefixes; anything not granted is
    denied. This is the scaffold's default binding -- an explicit, minimal
    mechanism, not a production policy language.
    """

    id: str
    grants: tuple[str, ...] = ()

    def may_access(self, uri: str) -> bool:
        """Return whether the caller may access the given source URI."""
        return any(uri.startswith(grant) for grant in self.grants)


class EvidenceProvider(Protocol):
    """Retrieval-assist source: ranks and surfaces supporting material.

    Providers receive the resolved safe candidates explicitly so retrieval
    can be scoped to them. Relevance is not authorization: the assembler
    still strips out-of-scope links and enforces the evidence authorization
    hook, so a provider can never expand authority.
    """

    def collect(
        self,
        request: ContextRequest,
        candidates: tuple[EngineeringAssertion, ...],
    ) -> tuple[Evidence, ...]:
        """Return candidate supporting evidence for the request."""
        ...


def redact_provenance(
    provenance: tuple[Provenance, ...],
    authorize: ProvenanceAuthorizationHook | None,
) -> tuple[Provenance, ...]:
    """Return caller-safe provenance, withholding restricted details."""
    if authorize is None:
        return provenance
    safe: list[Provenance] = []
    for entry in provenance:
        if authorize(entry):
            safe.append(entry)
        else:
            safe.append(
                replace(
                    entry,
                    uri=REDACTED_URI,
                    revision=None,
                    access_policy_ref=None,
                    last_validated_at=None,
                )
            )
    return tuple(safe)


def redacted_candidate_view(
    candidates: tuple[EngineeringAssertion, ...],
    authorize_provenance: ProvenanceAuthorizationHook,
) -> tuple[EngineeringAssertion, ...]:
    """Return candidates with caller-unauthorized provenance redacted.

    For use before an untrusted or external provider sees the candidate set:
    the provider gets the same authorized assertions, but provenance details
    the caller may not inspect are withheld (URIs, revisions, and policy
    references replaced by the redaction sentinel). Deterministic authority
    is preserved -- redaction never removes or reorders candidates.
    """
    return tuple(
        replace(
            assertion,
            provenance=redact_provenance(assertion.provenance, authorize_provenance),
        )
        for assertion in candidates
    )


class ExternalEvidenceProvider:
    """Boundary adapter for untrusted/external evidence providers.

    Satisfies the :class:`EvidenceProvider` protocol: ``collect`` redacts
    the candidate view with the caller's provenance hook *before* delegating
    to the wrapped provider, and records the exact view that crossed the
    boundary on the transport for audit.

    ``authorize_provenance`` is required -- an external boundary without a
    provenance policy is a misconfiguration and fails fast. The wrapped
    provider's output is still subject to the assembler's authorization
    boundaries: it cannot expand the authorized candidate set.
    """

    def __init__(
        self,
        provider: EvidenceProvider,
        authorize_provenance: ProvenanceAuthorizationHook,
        transport: Any | None = None,
    ) -> None:
        if authorize_provenance is None:
            raise TypeError(
                "ExternalEvidenceProvider requires a provenance hook; "
                "refusing to expose unredacted candidates to an external provider"
            )
        self._provider = provider
        self._authorize_provenance = authorize_provenance
        self._transport = transport

    def collect(
        self,
        request: ContextRequest,
        candidates: tuple[EngineeringAssertion, ...],
    ) -> tuple[Evidence, ...]:
        """Collect evidence over the redacted candidate view."""
        view = redacted_candidate_view(candidates, self._authorize_provenance)
        if self._transport is not None:
            self._transport.record(view)
        return self._provider.collect(request, view)


@dataclass(frozen=True, slots=True)
class ContextAssembler:
    """Combine trusted engineering memory with bounded retrieval assist."""

    providers: tuple[EvidenceProvider, ...] = ()
    authorize: AuthorizationHook | None = None
    authorize_evidence: EvidenceAuthorizationHook | None = None
    authorize_provenance: ProvenanceAuthorizationHook | None = None

    @classmethod
    def for_caller(
        cls,
        caller: Caller,
        providers: tuple[EvidenceProvider, ...] = (),
        *,
        authorize: AuthorizationHook | None = None,
        authorize_evidence: EvidenceAuthorizationHook | None = None,
        authorize_provenance: ProvenanceAuthorizationHook | None = None,
    ) -> ContextAssembler:
        """Build an assembler with all hooks bound to one authenticated caller.

        Any hook passed explicitly wins; omitted hooks default to the
        caller's grants instead of permissive behavior:

        - assertion: readable when the caller may access at least one of its
          provenance sources; an assertion with no provenance sources is
          unreadable (deny by default -- there is nothing to authorize
          against)
        - evidence: the item's source URI must be granted
        - provenance: an entry's URI must be granted, otherwise its details
          are redacted (mirroring the read_provenance decision)

        A caller with no grants is denied everything. The plain
        constructor keeps its permissive-when-omitted defaults for backward
        compatibility; caller-facing integrations should use this factory.
        """
        return cls(
            providers=providers,
            authorize=authorize
            or (
                lambda assertion: any(
                    caller.may_access(p.uri) for p in assertion.provenance
                )
            ),
            authorize_evidence=authorize_evidence
            or (lambda evidence: caller.may_access(evidence.uri)),
            authorize_provenance=authorize_provenance
            or (lambda provenance: caller.may_access(provenance.uri)),
        )

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
        candidates = result.active
        authorized_ids = {assertion.id for assertion in candidates}

        evidence: list[Evidence] = []
        for provider in self.providers:
            for item in provider.collect(request, candidates):
                # Strip links outside the safe set; drop orphaned items.
                safe_links = tuple(
                    link for link in item.relates_to if link in authorized_ids
                )
                if not safe_links:
                    continue
                item = replace(item, relates_to=safe_links)
                # Source authorization boundary, before ranking/budgeting.
                if self.authorize_evidence is not None and not self.authorize_evidence(
                    item
                ):
                    continue
                evidence.append(item)

        # Ranking is allowed here: it affects relevance, not authority.
        evidence.sort(
            key=lambda item: item.score if item.score is not None else 0.0,
            reverse=True,
        )
        evidence = evidence[: max(request.evidence_budget, 0)]

        # Provenance authorization is independent of assertion authorization.
        safe_assertions = tuple(
            replace(
                assertion,
                provenance=redact_provenance(
                    assertion.provenance, self.authorize_provenance
                ),
            )
            for assertion in candidates
        )
        safe_evidence = tuple(
            replace(
                item,
                provenance=redact_provenance(item.provenance, self.authorize_provenance),
            )
            for item in evidence
        )

        return AssembledContext(
            assertions=safe_assertions,
            evidence=tuple(safe_evidence),
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
