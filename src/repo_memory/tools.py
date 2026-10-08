"""Read-only MCP tool implementations (issue #4).

``memory_search`` and ``memory_get`` expose the deterministic engineering
context to coding agents. They are plain functions with JSON-serializable
I/O and no MCP/framework imports -- the MCP transport wiring lives outside
the core package (see ``mcp_server/``). Both tools run the complete path:

    tool call -> authenticate (#20) -> context assembly -> serialized response

Identity always comes from the trusted ``VerifiedSession`` plus the
server-side ``CallerDirectory``. Client-supplied identity or grants are
never accepted as authorization inputs. Missing or invalid credentials fail
closed; denied assertions are hidden entirely (``memory_get`` returns the
same ``not_found`` error whether the ID does not exist or the caller may
not read it).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import fields, replace
from datetime import UTC, datetime
from typing import Any

from repo_memory.auth import (
    AuthenticationError,
    AuthorizationError,
    CallerDirectory,
    VerifiedSession,
    assembler_for_session,
    authenticate,
)
from repo_memory.context import (
    REDACTED_URI,
    ContextAssembler,
    ContextRequest,
    Evidence,
    EvidenceProvider,
    RepositoryMetadata,
    redact_assertion,
)
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import AuthorizationHook, ResolutionContext
from repo_memory.serialization import assertion_to_dict

_SCOPE_FIELDS = frozenset(f.name for f in fields(Scope))


class ToolError(Exception):
    """Tool-level failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message}}


def parse_scope(raw: dict[str, Any]) -> Scope:
    """Parse a JSON scope object into a :class:`Scope`, rejecting unknown keys."""
    unknown = [key for key in raw if key not in _SCOPE_FIELDS]
    if unknown:
        raise ToolError(
            "invalid_scope", f"unknown scope keys: {sorted(unknown)!r}"
        )
    values = {
        key: (str(value) if value is not None else None)
        for key, value in raw.items()
    }
    return Scope(**values)


#: Assertion fields holding IDs of related assertions. All are filtered to
#: caller-readable targets before serialization so denied assertion IDs are
#: never exposed through relationship fields.
_LINK_FIELDS = ("overrides", "supersedes", "superseded_by", "conflicts_with")


def filter_relationship_links(
    assertion: EngineeringAssertion,
    authorize: AuthorizationHook | None,
    by_id: dict[str, EngineeringAssertion],
) -> EngineeringAssertion:
    """Withhold relationship links to assertions the caller may not read.

    Lifecycle status is retained, but any ID in the relationship fields that
    resolves to a denied (or unknown) assertion is removed -- denied
    assertion existence is never revealed through ``overrides``,
    ``supersedes``, ``superseded_by`` or ``conflicts_with``.
    """
    if authorize is None:
        return assertion

    def readable(ref_id: str) -> bool:
        target = by_id.get(ref_id)
        return target is not None and authorize(target)

    filtered = {
        field: tuple(ref for ref in getattr(assertion, field) if readable(ref))
        for field in _LINK_FIELDS
    }
    if all(
        filtered[field] == getattr(assertion, field) for field in _LINK_FIELDS
    ):
        return assertion
    return replace(assertion, **filtered)


def _provenance_to_dict(provenance: Provenance) -> dict[str, Any]:
    return {
        "type": provenance.type,
        "uri": provenance.uri,
        "revision": provenance.revision,
        "access_policy_ref": provenance.access_policy_ref,
        "last_validated_at": (
            provenance.last_validated_at.isoformat().replace("+00:00", "Z")
            if provenance.last_validated_at is not None
            else None
        ),
        # Explicit marker matching docs/retrieval-contract.md's redacted shape.
        "redacted": provenance.uri == REDACTED_URI,
    }


def serialize_assertion(assertion: EngineeringAssertion) -> dict[str, Any]:
    """Serialize a caller-safe assertion with explicit redaction markers."""
    payload = assertion_to_dict(assertion)
    payload["provenance"] = [
        _provenance_to_dict(entry) for entry in assertion.provenance
    ]
    return payload


def serialize_evidence(item: Evidence) -> dict[str, Any]:
    """Serialize caller-safe evidence with redaction markers."""
    return {
        "uri": item.uri,
        "kind": item.kind,
        "snippet": item.snippet,
        "relates_to": list(item.relates_to),
        "score": item.score,
        "provenance": [_provenance_to_dict(entry) for entry in item.provenance],
    }


def memory_search(
    session: VerifiedSession | None,
    directory: CallerDirectory,
    assertions: Iterable[EngineeringAssertion],
    task: str,
    scope: Scope,
    *,
    when: datetime | None = None,
    repository: RepositoryMetadata | None = None,
    evidence_budget: int = 10,
    providers: tuple[EvidenceProvider, ...] = (),
    external_providers: tuple[EvidenceProvider, ...] = (),
    boundary_transport: Any | None = None,
) -> dict[str, Any]:
    """Search authorized active assertions for a task and scope.

    Runs the full retrieval pipeline (identity -> scope -> authorization ->
    lifecycle -> applicability -> ranking -> budget -> redaction) and returns
    the caller-safe serialized response. ``task`` is a relevance hint only;
    it never widens authority.
    """
    if not task or not task.strip():
        raise ToolError("invalid_task", "task must be a non-empty string")
    if evidence_budget < 0:
        raise ToolError(
            "invalid_budget", "evidence_budget must not be negative"
        )
    assembler = assembler_for_session(
        session,
        directory,
        providers=providers,
        external_providers=external_providers,
        boundary_transport=boundary_transport,
    )
    request = ContextRequest(
        task=task,
        resolution=ResolutionContext(
            scope=scope, when=when if when is not None else datetime.now(UTC)
        ),
        repository=repository,
        evidence_budget=evidence_budget,
    )
    corpus = tuple(assertions)
    by_id = {assertion.id: assertion for assertion in corpus}
    context = assembler.assemble(corpus, request)
    # Relationship links are filtered to caller-readable targets so denied
    # assertion IDs never leak through superseded_by / conflicts_with / etc.
    safe_assertions = tuple(
        filter_relationship_links(a, assembler.authorize, by_id)
        for a in context.assertions
    )
    return {
        "assertions": [serialize_assertion(a) for a in safe_assertions],
        "evidence": [serialize_evidence(e) for e in context.evidence],
        "conflicts": [list(pair) for pair in context.conflicts],
    }


def memory_get(
    session: VerifiedSession | None,
    directory: CallerDirectory,
    assertions: Iterable[EngineeringAssertion],
    assertion_id: str,
) -> dict[str, Any]:
    """Fetch one assertion by ID with caller-safe provenance.

    The caller must be authorized to read the assertion; otherwise the
    response is indistinguishable from a missing ID, hiding unauthorized
    assertion existence. Lifecycle status is retained in the payload
    (``status``), but relationship links (``superseded_by``,
    ``conflicts_with``, ``overrides``, ``supersedes``) are filtered to
    caller-readable targets: this is a direct fetch, and authorization --
    not lifecycle -- is the security boundary.
    """
    if not assertion_id or not assertion_id.strip():
        raise ToolError(
            "invalid_id", "assertion_id must be a non-empty string"
        )
    caller = authenticate(session, directory)
    assembler = ContextAssembler.for_caller(caller)
    corpus = tuple(assertions)
    matches = [a for a in corpus if a.id == assertion_id]
    if not matches:
        raise ToolError(
            "not_found", "assertion not found or not accessible"
        )
    assertion = matches[0]
    # Same generic error for denied as for missing: existence stays hidden.
    if assembler.authorize is not None and not assembler.authorize(assertion):
        raise ToolError(
            "not_found", "assertion not found or not accessible"
        )
    # Lifecycle status is retained, but relationship links to denied
    # assertions are withheld.
    by_id = {a.id: a for a in corpus}
    safe = filter_relationship_links(assertion, assembler.authorize, by_id)
    safe = redact_assertion(safe, assembler.authorize_provenance)
    return {"assertion": serialize_assertion(safe)}


TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "memory_search",
        "description": (
            "Search durable engineering memory for the caller's task and "
            "target scope. Returns authorized active assertions with "
            "caller-safe provenance plus bounded supporting evidence. "
            "The task text guides relevance only; it never widens authority."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "What the agent is working on.",
                },
                "scope": {
                    "type": "object",
                    "description": (
                        "Target engineering scope; keys: organization, "
                        "domain, system, repository, component, branch, "
                        "pull_request."
                    ),
                    "additionalProperties": {"type": "string"},
                },
                "evidence_budget": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 10,
                    "description": "Maximum supporting evidence items.",
                },
                "session_token": {
                    "type": "string",
                    "description": (
                        "Deployment-issued credential; resolved to a "
                        "verified session server-side."
                    ),
                },
            },
            "required": ["task", "scope", "session_token"],
        },
    },
    {
        "name": "memory_get",
        "description": (
            "Fetch one engineering assertion by ID with caller-safe "
            "provenance. Returns not_found when the ID does not exist or "
            "the caller may not read it; existence of denied assertions is "
            "never revealed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "assertion_id": {"type": "string"},
                "session_token": {
                    "type": "string",
                    "description": (
                        "Deployment-issued credential; resolved to a "
                        "verified session server-side."
                    ),
                },
            },
            "required": ["assertion_id", "session_token"],
        },
    },
)


def handle_tool_call(
    name: str,
    arguments: dict[str, Any],
    *,
    resolve_session: Any,
    directory: CallerDirectory,
    assertions: Iterable[EngineeringAssertion],
) -> dict[str, Any]:
    """Dispatch one MCP tool call to the core implementation.

    ``resolve_session`` maps the client's ``session_token`` to a
    ``VerifiedSession`` (or ``None``); credential verification stays
    deployment-owned. Unknown tool names and tool failures become
    ``ToolError`` payloads.
    """
    if name not in ("memory_search", "memory_get"):
        raise ToolError("unknown_tool", f"unknown tool: {name!r}")
    session = resolve_session(arguments.get("session_token"))
    try:
        if name == "memory_search":
            return memory_search(
                session,
                directory,
                assertions,
                task=arguments.get("task", ""),
                scope=parse_scope(arguments.get("scope", {})),
                evidence_budget=int(arguments.get("evidence_budget", 10)),
            )
        return memory_get(
            session,
            directory,
            assertions,
            assertion_id=arguments.get("assertion_id", ""),
        )
    except ToolError as exc:
        return exc.to_dict()
    except AuthenticationError as exc:
        # Fail closed, but as a well-formed tool error rather than a crash.
        return ToolError("unauthenticated", str(exc)).to_dict()
    except AuthorizationError as exc:
        return ToolError("forbidden", str(exc)).to_dict()
