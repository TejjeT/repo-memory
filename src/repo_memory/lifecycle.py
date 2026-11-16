"""Governed assertion lifecycle (issue #3).

Explicit, authorized, deterministic transitions over the existing
Engineering Assertion contract. See ``docs/lifecycle.md`` for the rules.

Design constraints kept here:

- no LLM decides anything; every rule is a table lookup or a comparison
- identity comes from :func:`repo_memory.auth.authenticate`, never from the
  request body
- a transition changes ``status`` and relationship links only; content, scope
  and provenance are never rewritten
- every transition appends one immutable :class:`GovernanceEvent`
- storage is a small protocol; this module ships only an in-memory reference
  store, vendor stores live under ``adapters/``
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from repo_memory.auth import CallerDirectory, VerifiedSession, authenticate
from repo_memory.context import REDACTED_URI, Caller
from repo_memory.models import EngineeringAssertion, Scope

#: Allowed status changes. Anything absent is rejected.
TRANSITIONS: dict[str, dict[str, str]] = {
    "approve": {"proposed": "approved"},
    "reject": {"proposed": "rejected"},
    "supersede": {"approved": "superseded"},
    "expire": {"approved": "expired"},
    "archive": {
        "proposed": "archived",
        "approved": "archived",
        "rejected": "archived",
        "superseded": "archived",
        "expired": "archived",
    },
}

#: Role required for each action. ``propose`` needs only ``proposer``.
REQUIRED_ROLE = {
    "propose": "proposer",
    "approve": "approver",
    "reject": "approver",
    "supersede": "approver",
    "expire": "approver",
    "archive": "approver",
}


class LifecycleError(Exception):
    """A lifecycle operation was refused. Nothing was written.

    ``code`` is stable and machine-readable:

    - ``not_found``     unknown ID, or one the caller may not read (identical
                        on purpose, so existence is not revealed)
    - ``forbidden``     the caller can read it but lacks the role
    - ``invalid``       the request breaks a documented rule
    - ``conflict``      the assertion is not in a state that allows the action
    - ``already_done``  the exact same decision is already recorded
    - ``concurrent``    another writer changed the record first; retry
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ConcurrentModification(Exception):
    """Raised by a store when an expected version no longer matches."""


@dataclass(frozen=True, slots=True)
class SourceRevision:
    """The evidence state a decision was made against."""

    uri: str
    revision: str | None = None


@dataclass(frozen=True, slots=True)
class GovernanceEvent:
    """One immutable governance decision."""

    action: str
    assertion_id: str
    actor: str
    at: datetime
    from_status: str | None
    to_status: str
    reason: str
    source_revisions: tuple[SourceRevision, ...] = ()
    related_ids: tuple[str, ...] = ()
    auth_method: str = "unspecified"


@dataclass(frozen=True, slots=True)
class Stored:
    """An assertion with its optimistic-concurrency version (1 = first write)."""

    assertion: EngineeringAssertion
    version: int


class LifecycleStore(Protocol):
    """Backend-neutral storage contract for governed writes."""

    def load(self, assertion_id: str) -> Stored | None:
        """Return the stored assertion and version, or ``None``."""
        ...

    def commit(
        self,
        writes: Iterable[tuple[EngineeringAssertion, int]],
        events: Iterable[GovernanceEvent],
    ) -> None:
        """Apply all writes and append all events, or none.

        Each write carries the version the caller read (0 = must not exist).
        Raise :class:`ConcurrentModification` on any mismatch.
        """
        ...

    def history(self, assertion_id: str) -> tuple[GovernanceEvent, ...]:
        """Return events for one assertion, oldest first."""
        ...

    def assertions(self) -> tuple[EngineeringAssertion, ...]:
        """Return every stored assertion, any status."""
        ...


class InMemoryLifecycleStore:
    """Reference store. Commits are atomic within one process."""

    def __init__(self) -> None:
        self._records: dict[str, Stored] = {}
        self._events: list[GovernanceEvent] = []

    def load(self, assertion_id: str) -> Stored | None:
        return self._records.get(assertion_id)

    def commit(
        self,
        writes: Iterable[tuple[EngineeringAssertion, int]],
        events: Iterable[GovernanceEvent],
    ) -> None:
        writes = list(writes)
        for assertion, expected in writes:
            current = self._records.get(assertion.id)
            if (current.version if current else 0) != expected:
                raise ConcurrentModification(assertion.id)
        for assertion, expected in writes:
            self._records[assertion.id] = Stored(assertion, expected + 1)
        self._events.extend(events)

    def history(self, assertion_id: str) -> tuple[GovernanceEvent, ...]:
        return tuple(e for e in self._events if e.assertion_id == assertion_id)

    def assertions(self) -> tuple[EngineeringAssertion, ...]:
        return tuple(record.assertion for record in self._records.values())


class LifecycleAuthority(Protocol):
    """Server-side decision: may this subject act in this role on this scope?"""

    def has_role(self, subject: str, role: str, scope: Scope) -> bool: ...


@dataclass(frozen=True, slots=True)
class ScopeRoleAuthority:
    """Reference authority: explicit (subject, role, scope) grants.

    A grant on a scope covers its descendants. There is no default grant and
    no wildcard subject: an absent entry is a denial.
    """

    grants: tuple[tuple[str, str, Scope], ...]

    def has_role(self, subject: str, role: str, scope: Scope) -> bool:
        return any(
            who == subject and held == role and granted.applies_to(scope)
            for who, held, granted in self.grants
        )


@dataclass(frozen=True, slots=True)
class LifecycleService:
    """Authorized lifecycle operations over a :class:`LifecycleStore`."""

    store: LifecycleStore
    directory: CallerDirectory
    authority: LifecycleAuthority
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    #: Separation of duties: the proposer may not approve their own proposal.
    allow_self_approval: bool = False

    # -- writes ------------------------------------------------------------

    def propose(
        self, session: VerifiedSession | None, assertion: EngineeringAssertion, reason: str
    ) -> GovernanceEvent:
        """Record a new assertion as ``proposed``. It is not retrievable as
        active guidance until approved."""

        caller = authenticate(session, self.directory)
        _require_reason(reason)
        if not assertion.provenance:
            raise LifecycleError("invalid", "a proposal needs at least one provenance source")
        if assertion.scope.organization is None:
            raise LifecycleError("invalid", "a proposal needs an organization scope")
        if assertion.superseded_by:
            raise LifecycleError("invalid", "a proposal cannot arrive already superseded")
        self._require_role(caller, "propose", assertion.scope)
        # A reference to something the proposer cannot read is refused the
        # same way as a reference to nothing, so links cannot probe existence.
        for ref in (*assertion.supersedes, *assertion.overrides, *assertion.conflicts_with):
            self._readable(caller, ref)
        if self.store.load(assertion.id) is not None:
            raise LifecycleError("conflict", f"{assertion.id} already exists")

        proposed = replace(assertion, status="proposed")
        event = self._event("propose", proposed, caller, session, None, "proposed", reason)
        self._commit([(proposed, 0)], [event])
        return event

    def approve(
        self, session: VerifiedSession | None, assertion_id: str, reason: str
    ) -> GovernanceEvent:
        """Approve a proposal. Assertions it ``supersedes`` are marked
        superseded in the same commit, so no stale predecessor stays approved."""

        caller = authenticate(session, self.directory)
        stored = self._transition_target(caller, "approve", assertion_id, reason)
        target = stored.assertion
        history = self.store.history(assertion_id)
        proposer = history[0].actor if history else None
        if not self.allow_self_approval and proposer == caller.id:
            raise LifecycleError("forbidden", "the proposer may not approve their own proposal")

        writes = [(replace(target, status="approved"), stored.version)]
        events = [
            self._event(
                "approve", target, caller, session, "proposed", "approved", reason,
                related=target.supersedes,
            )
        ]
        for old_id in target.supersedes:
            old = self._readable(caller, old_id)
            if old.assertion.status != "approved":
                raise LifecycleError(
                    "conflict",
                    f"{old_id} is {old.assertion.status}; only approved can be superseded",
                )
            if not old.assertion.scope.same_organization(target.scope):
                raise LifecycleError("invalid", "supersession may not cross organizations")
            self._require_role(caller, "supersede", old.assertion.scope)
            successors = tuple(dict.fromkeys((*old.assertion.superseded_by, target.id)))
            writes.append(
                (replace(old.assertion, status="superseded", superseded_by=successors), old.version)
            )
            events.append(
                self._event(
                    "supersede", old.assertion, caller, session, "approved", "superseded",
                    reason, related=(target.id,),
                )
            )
        self._commit(writes, events)
        return events[0]

    def supersede(
        self, session: VerifiedSession | None, old_id: str, new_id: str, reason: str
    ) -> GovernanceEvent:
        """Mark an approved assertion as superseded by another approved one.

        Both records are linked in one commit. Use this to repair a
        predecessor that was left approved; a new successor normally declares
        ``supersedes`` in its proposal and is handled by :meth:`approve`.
        """

        caller = authenticate(session, self.directory)
        if old_id == new_id:
            raise LifecycleError("invalid", "an assertion cannot supersede itself")
        old = self._transition_target(caller, "supersede", old_id, reason)
        new = self._readable(caller, new_id)
        self._require_role(caller, "supersede", new.assertion.scope)
        if new.assertion.status != "approved":
            raise LifecycleError("conflict", f"{new_id} is not approved")
        if not old.assertion.scope.same_organization(new.assertion.scope):
            raise LifecycleError("invalid", "supersession may not cross organizations")
        successors = tuple(dict.fromkeys((*old.assertion.superseded_by, new_id)))
        predecessors = tuple(dict.fromkeys((*new.assertion.supersedes, old_id)))
        event = self._event(
            "supersede", old.assertion, caller, session, "approved", "superseded", reason,
            related=(new_id,),
        )
        self._commit(
            [
                (
                    replace(old.assertion, status="superseded", superseded_by=successors),
                    old.version,
                ),
                (replace(new.assertion, supersedes=predecessors), new.version),
            ],
            [event],
        )
        return event

    def reject(
        self, session: VerifiedSession | None, assertion_id: str, reason: str
    ) -> GovernanceEvent:
        return self._simple(session, "reject", assertion_id, reason)

    def expire(
        self, session: VerifiedSession | None, assertion_id: str, reason: str
    ) -> GovernanceEvent:
        return self._simple(session, "expire", assertion_id, reason)

    def archive(
        self, session: VerifiedSession | None, assertion_id: str, reason: str
    ) -> GovernanceEvent:
        return self._simple(session, "archive", assertion_id, reason)

    # -- reads -------------------------------------------------------------

    def history(self, session: VerifiedSession | None, assertion_id: str) -> list[dict[str, Any]]:
        """Return caller-safe governance history, oldest first.

        Source URIs the caller may not access are redacted, and related IDs
        the caller may not read are withheld.
        """

        caller = authenticate(session, self.directory)
        self._readable(caller, assertion_id)
        safe: list[dict[str, Any]] = []
        for event in self.store.history(assertion_id):
            related = []
            for ref in event.related_ids:
                other = self.store.load(ref)
                if other is not None and _may_read(caller, other.assertion):
                    related.append(ref)
            safe.append(
                {
                    "action": event.action,
                    "assertion_id": event.assertion_id,
                    "actor": event.actor,
                    "at": event.at.isoformat().replace("+00:00", "Z"),
                    "from_status": event.from_status,
                    "to_status": event.to_status,
                    "reason": event.reason,
                    "related_ids": related,
                    "source_revisions": [
                        {"uri": s.uri, "revision": s.revision}
                        if caller.may_access(s.uri)
                        else {"uri": REDACTED_URI, "revision": None}
                        for s in event.source_revisions
                    ],
                }
            )
        return safe

    # -- internals ---------------------------------------------------------

    def _simple(
        self, session: VerifiedSession | None, action: str, assertion_id: str, reason: str
    ) -> GovernanceEvent:
        caller = authenticate(session, self.directory)
        stored = self._transition_target(caller, action, assertion_id, reason)
        target = stored.assertion
        to_status = TRANSITIONS[action][target.status]
        event = self._event(action, target, caller, session, target.status, to_status, reason)
        self._commit([(replace(target, status=to_status), stored.version)], [event])
        return event

    def _transition_target(
        self, caller: Caller, action: str, assertion_id: str, reason: str
    ) -> Stored:
        _require_reason(reason)
        stored = self._readable(caller, assertion_id)
        self._require_role(caller, action, stored.assertion.scope)
        allowed = TRANSITIONS[action]
        status = stored.assertion.status
        if status not in allowed:
            if status == next(iter(allowed.values())):
                raise LifecycleError("already_done", f"{assertion_id} is already {status}")
            raise LifecycleError("conflict", f"cannot {action} an assertion that is {status}")
        return stored

    def _readable(self, caller: Caller, assertion_id: str) -> Stored:
        stored = self.store.load(assertion_id)
        if stored is None or not _may_read(caller, stored.assertion):
            raise LifecycleError("not_found", "assertion not found or not accessible")
        return stored

    def _require_role(self, caller: Caller, action: str, scope: Scope) -> None:
        if not self.authority.has_role(caller.id, REQUIRED_ROLE[action], scope):
            raise LifecycleError("forbidden", f"caller may not {action} in this scope")

    def _event(
        self,
        action: str,
        assertion: EngineeringAssertion,
        caller: Caller,
        session: VerifiedSession | None,
        from_status: str | None,
        to_status: str,
        reason: str,
        related: tuple[str, ...] = (),
    ) -> GovernanceEvent:
        return GovernanceEvent(
            action=action,
            assertion_id=assertion.id,
            actor=caller.id,
            at=self.clock(),
            from_status=from_status,
            to_status=to_status,
            reason=reason.strip(),
            source_revisions=tuple(
                SourceRevision(p.uri, p.revision) for p in assertion.provenance
            ),
            related_ids=tuple(related),
            auth_method=session.method if session else "unspecified",
        )

    def _commit(
        self, writes: list[tuple[EngineeringAssertion, int]], events: list[GovernanceEvent]
    ) -> None:
        try:
            self.store.commit(writes, events)
        except ConcurrentModification as exc:
            raise LifecycleError(
                "concurrent", f"{exc} changed since it was read; nothing was written"
            ) from exc


def _may_read(caller: Caller, assertion: EngineeringAssertion) -> bool:
    # Same default as ContextAssembler.for_caller: readable when at least one
    # provenance source is granted; no provenance means unreadable.
    return any(caller.may_access(p.uri) for p in assertion.provenance)


def _require_reason(reason: str) -> None:
    if not reason or not reason.strip():
        raise LifecycleError("invalid", "a reason is required for every governance decision")
