"""Authenticated caller boundary (issue #20).

``Caller`` (see ``repo_memory.context``) is a trusted core input: anything
that constructs one directly decides its own grants. That is fine for
in-process use, but a caller-facing deployment (remote API, MCP server)
must not let the client choose its identity or permissions.

This module is the boundary between the deployment's authentication layer
and the core. The deployment verifies credentials by its own means (session
store, OIDC, API-key lookup -- core defines no identity provider) and hands
the boundary a :class:`VerifiedSession`. The boundary resolves that session
to a :class:`Caller` using only server-side inputs:

- missing or unresolvable sessions fail closed (:class:`AuthenticationError`)
- client-supplied caller ids or grants are validated against the resolved
  identity and rejected when they would widen access
  (:class:`AuthorizationError`)
- the returned :class:`Caller` always carries the server-derived grants;
  client claims are validated, never applied

There is deliberately no permissive fallback on this path: the plain
``ContextAssembler`` constructor keeps its backward-compatible defaults,
but authenticated integrations must enter through :func:`authenticate` or
:func:`assembler_for_session`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from repo_memory.context import Caller, ContextAssembler, EvidenceProvider


class AuthenticationError(Exception):
    """Raised when credentials are missing or cannot be verified. Fail closed."""


class AuthorizationError(Exception):
    """Raised when a verified caller attempts to widen its access."""


@dataclass(frozen=True, slots=True)
class VerifiedSession:
    """Server-verified authentication. Produced by the deployment's identity
    layer, never from client input.

    ``subject`` is the verified identity (user, team, service account).
    ``method`` records how verification happened (``"session-cookie"``,
    ``"oidc"``, ``"api-key"``, ...) for audit; core does not interpret it.
    """

    subject: str
    authenticated_at: datetime
    method: str = "unspecified"


class CallerDirectory(Protocol):
    """Server-side mapping from verified subject to source grants.

    Deployments implement this against their own authorization source
    (group membership, repository permissions, policy service). Unknown
    subjects must raise :exc:`LookupError`; the boundary converts that to
    :class:`AuthenticationError` so existence is not leaked.
    """

    def grants_for(self, subject: str) -> tuple[str, ...]:
        """Return the source URI prefixes granted to the subject."""
        ...


def resolve_caller(
    session: VerifiedSession | None,
    directory: CallerDirectory,
) -> Caller:
    """Resolve a verified session to a caller using only server-side inputs.

    ``None`` sessions and unresolvable subjects raise
    :class:`AuthenticationError`. The grants always come from the directory;
    nothing the client sent is consulted.
    """
    if session is None or not session.subject:
        raise AuthenticationError("missing credentials")
    try:
        grants = directory.grants_for(session.subject)
    except LookupError as exc:
        raise AuthenticationError("unknown subject") from exc
    return Caller(id=session.subject, grants=tuple(grants))


def authenticate(
    session: VerifiedSession | None,
    directory: CallerDirectory,
    *,
    claimed_caller_id: str | None = None,
    claimed_grants: Iterable[str] = (),
) -> Caller:
    """Authenticate a request and return the server-derived caller.

    Optional client claims are validated against the resolved identity and
    then discarded -- the returned caller always carries the directory's
    grants:

    - a claimed caller id different from the verified subject is rejected
    - claimed grants that are not a subset of the derived grants are
      rejected as a widening attempt
    """
    caller = resolve_caller(session, directory)
    if claimed_caller_id is not None and claimed_caller_id != caller.id:
        raise AuthorizationError(
            f"caller id {claimed_caller_id!r} does not match verified subject"
        )
    derived = set(caller.grants)
    widening = [grant for grant in claimed_grants if grant not in derived]
    if widening:
        raise AuthorizationError(
            f"client-supplied grants would widen access: {widening!r}"
        )
    return caller


def assembler_for_session(
    session: VerifiedSession | None,
    directory: CallerDirectory,
    providers: tuple[EvidenceProvider, ...] = (),
    *,
    claimed_caller_id: str | None = None,
    claimed_grants: Iterable[str] = (),
) -> ContextAssembler:
    """Build a caller-bound assembler for one authenticated request.

    This is the single entry point for authenticated paths: identity comes
    from the session, hooks bind to that same identity, and there is no
    permissive fallback.
    """
    caller = authenticate(
        session,
        directory,
        claimed_caller_id=claimed_caller_id,
        claimed_grants=claimed_grants,
    )
    return ContextAssembler.for_caller(caller, providers=providers)


class BoundaryTransport(Protocol):
    """Audit hook recording what crossed an external-provider boundary."""

    def record(self, view: tuple[object, ...]) -> None:
        """Record the exact candidate view handed to the provider."""
        ...


@dataclass
class RecordingTransport:
    """Test/audit transport capturing every outbound candidate view.

    Deployments can substitute a real audit sink behind the same protocol;
    tests use this to prove restricted data never crossed the boundary.
    """

    sent_views: list[tuple[object, ...]] = field(default_factory=list)

    def record(self, view: tuple[object, ...]) -> None:
        self.sent_views.append(view)
