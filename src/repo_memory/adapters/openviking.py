"""OpenViking adapter for Engineering Assertions.

The adapter depends on a tiny client protocol instead of importing OpenViking's
SDK directly. Any compatible SyncHTTPClient can be injected at runtime.

OpenViking is used for shared resource storage, ACL enforcement, and indexing.
repo-memory remains responsible for engineering applicability and lifecycle
semantics.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Protocol

from repo_memory.lifecycle import (
    ConcurrentModification,
    GovernanceEvent,
    SourceRevision,
    Stored,
)
from repo_memory.models import EngineeringAssertion
from repo_memory.policy import ResolutionContext, ResolutionResult, resolve_assertions
from repo_memory.serialization import assertion_from_json_dict, assertion_to_dict


class OpenVikingClient(Protocol):
    """Minimal OpenViking client surface required by this adapter."""

    def write(
        self,
        uri: str,
        content: str,
        mode: str = "replace",
        options: dict[str, Any] | None = None,
    ) -> Any:
        """Write a shared resource."""

    def read(self, uri: str) -> str:
        """Read a shared resource file."""

    def ls(
        self,
        uri: str,
        simple: bool = False,
        recursive: bool = False,
        **kwargs: Any,
    ) -> list[Any]:
        """List shared resource entries."""


AclResolver = Callable[[EngineeringAssertion], dict[str, Any] | None]
AuthorizationHook = Callable[[EngineeringAssertion], bool]

# Compatibility shim: the live OpenViking server raises authorization denials
# (e.g. PermissionDeniedError) on ls/read of restricted paths instead of
# returning entries marked {"access": "denied"}. Matching by class name keeps
# this adapter decoupled from the OpenViking SDK, which is deliberate for the
# experiment — but it is brittle if the SDK ever renames its error types. A
# future SDK wrapper or injectable error classifier would be safer.
# See docs/openviking-adapter.md ("Known v0 limitations").
_ACCESS_DENIED_ERROR_NAMES = frozenset(
    {"PermissionDeniedError", "AccessDeniedError", "ForbiddenError"}
)


def _is_access_denied(error: BaseException) -> bool:
    """Return True when ``error`` is an OpenViking authorization denial."""
    return type(error).__name__ in _ACCESS_DENIED_ERROR_NAMES


@dataclass(frozen=True, slots=True)
class OpenVikingAdapterConfig:
    """Configuration for assertion storage inside OpenViking."""

    root_uri: str = "viking://resources/repo-memory/assertions"

    def normalized_root(self) -> str:
        return self.root_uri.rstrip("/")


class OpenVikingAssertionStore:
    """Store and retrieve Engineering Assertions using OpenViking resources."""

    def __init__(
        self,
        client: OpenVikingClient,
        *,
        config: OpenVikingAdapterConfig | None = None,
        acl_resolver: AclResolver | None = None,
    ) -> None:
        self._client = client
        self._config = config or OpenVikingAdapterConfig()
        self._acl_resolver = acl_resolver

    def put(self, assertion: EngineeringAssertion) -> str:
        """Write an assertion as canonical JSON and return its Viking URI."""

        uri = assertion_uri(self._config.normalized_root(), assertion)
        payload = json.dumps(assertion_to_dict(assertion), indent=2, sort_keys=True)

        options = {
            "tags": assertion_tags(assertion),
            "tag_mode": "replace",
        }
        if self._acl_resolver is not None:
            acl = self._acl_resolver(assertion)
            if acl is not None:
                options["acl"] = acl

        self._client.write(
            uri=uri,
            content=payload,
            mode="replace",
            options=options,
        )
        return uri

    def list_for_organization(self, organization: str) -> tuple[EngineeringAssertion, ...]:
        """Load readable assertions within one organization.

        Traversal is done level by level instead of relying on the server's
        recursive listing: live-server verification showed recursive ``ls``
        may return descendant directories without their files. OpenViking
        ACLs are expected to filter unreadable descendants. Entries
        explicitly marked as access denied are ignored, denied directories
        are not descended into, and authorization denials raised by the live
        server during listing or reading are skipped rather than propagated.
        """

        root = f"{self._config.normalized_root()}/{_slug(organization)}/"

        assertions: list[EngineeringAssertion] = []
        for entry in _walk_files(self._client, root):
            uri = _entry_uri(entry)
            if uri is None or not uri.endswith(".json"):
                continue
            if _entry_access_denied(entry):
                continue

            try:
                payload = json.loads(self._client.read(uri))
            except Exception as exc:
                # The file may have become unreadable between listing and
                # reading; the live server raises instead of marking entries.
                if _is_access_denied(exc):
                    continue
                raise
            assertions.append(assertion_from_json_dict(payload))

        return tuple(assertions)

    def resolve(
        self,
        context: ResolutionContext,
        *,
        authorize: AuthorizationHook | None = None,
    ) -> ResolutionResult:
        """Load the organization candidate set and apply repo-memory policy."""

        organization = context.scope.organization
        if organization is None:
            raise ValueError("OpenViking resolution requires organization scope")

        assertions = self.list_for_organization(organization)
        return resolve_assertions(assertions, context, authorize=authorize)


class OpenVikingLifecycleStore:
    """``LifecycleStore`` over OpenViking resources (issue #3).

    Each assertion keeps its canonical JSON where :class:`OpenVikingAssertionStore`
    writes it, so existing reads are unchanged. Version and governance events
    live in a sidecar under ``governance_root_uri``, written with the same ACL.

    **Not safe for concurrent writers.** The client protocol has no
    compare-and-swap and no multi-resource transaction: versions are checked
    and then written, and a commit touching two assertions is two writes. A
    single governing writer is required until the backend offers a
    conditional write. Sidecars are written last, so an interrupted commit
    leaves a version that still matches and can be retried.
    """

    def __init__(
        self,
        client: OpenVikingClient,
        *,
        config: OpenVikingAdapterConfig | None = None,
        acl_resolver: AclResolver | None = None,
        governance_root_uri: str = "viking://resources/repo-memory/governance",
    ) -> None:
        self._client = client
        self._assertions = OpenVikingAssertionStore(
            client, config=config, acl_resolver=acl_resolver
        )
        self._acl_resolver = acl_resolver
        self._root = governance_root_uri.rstrip("/")

    def load(self, assertion_id: str) -> Stored | None:
        sidecar = self._sidecar(assertion_id)
        if sidecar is None:
            return None
        payload = json.loads(self._client.read(sidecar["uri"]))
        return Stored(assertion_from_json_dict(payload), sidecar["version"])

    def commit(
        self,
        writes: Iterable[tuple[EngineeringAssertion, int]],
        events: Iterable[GovernanceEvent],
    ) -> None:
        writes, events = list(writes), list(events)
        sidecars = {a.id: self._sidecar(a.id) for a, _ in writes}
        for assertion, expected in writes:
            current = sidecars[assertion.id]
            if (current["version"] if current else 0) != expected:
                raise ConcurrentModification(assertion.id)
        uris = {a.id: self._assertions.put(a) for a, _ in writes}
        for assertion, expected in writes:
            previous = sidecars[assertion.id] or {"events": []}
            added = [_event_to_dict(e) for e in events if e.assertion_id == assertion.id]
            options: dict[str, Any] = {}
            acl = self._acl_resolver(assertion) if self._acl_resolver else None
            if acl is not None:
                options["acl"] = acl
            self._client.write(
                uri=self._sidecar_uri(assertion.id),
                content=json.dumps(
                    {
                        "version": expected + 1,
                        "uri": uris[assertion.id],
                        "events": [*previous["events"], *added],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                mode="replace",
                options=options,
            )

    def history(self, assertion_id: str) -> tuple[GovernanceEvent, ...]:
        sidecar = self._sidecar(assertion_id)
        return tuple(_event_from_dict(e) for e in sidecar["events"]) if sidecar else ()

    def assertions(self) -> tuple[EngineeringAssertion, ...]:
        found: list[EngineeringAssertion] = []
        for entry in _walk_files(self._client, self._root + "/"):
            uri = _entry_uri(entry)
            if uri is None or not uri.endswith(".json") or _entry_access_denied(entry):
                continue
            try:
                sidecar = json.loads(self._client.read(uri))
                payload = json.loads(self._client.read(sidecar["uri"]))
            except Exception as exc:
                if _is_access_denied(exc):
                    continue
                raise
            found.append(assertion_from_json_dict(payload))
        return tuple(found)

    def _sidecar_uri(self, assertion_id: str) -> str:
        return f"{self._root}/{_slug(assertion_id)}.json"

    def _sidecar(self, assertion_id: str) -> dict[str, Any] | None:
        try:
            return json.loads(self._client.read(self._sidecar_uri(assertion_id)))
        except Exception as exc:
            # Absent and unreadable are both "nothing to govern here".
            if isinstance(exc, KeyError | FileNotFoundError) or _is_access_denied(exc):
                return None
            if "NotFound" in type(exc).__name__:
                return None
            raise


def _event_to_dict(event: GovernanceEvent) -> dict[str, Any]:
    raw = asdict(event)
    raw["at"] = event.at.isoformat()
    return raw


def _event_from_dict(raw: dict[str, Any]) -> GovernanceEvent:
    return GovernanceEvent(
        **{
            **raw,
            "at": datetime.fromisoformat(raw["at"]),
            "source_revisions": tuple(SourceRevision(**s) for s in raw["source_revisions"]),
            "related_ids": tuple(raw["related_ids"]),
        }
    )


def assertion_uri(root_uri: str, assertion: EngineeringAssertion) -> str:
    """Return a stable shared-resource URI for an assertion."""

    scope = assertion.scope
    if scope.organization is None:
        raise ValueError("OpenViking storage requires assertion organization scope")

    segments = [
        _slug(scope.organization),
        _slug(scope.domain or "_"),
        _slug(scope.system or "_"),
        _slug(scope.repository or "_"),
    ]
    directory = "/".join(segments)
    return f"{root_uri.rstrip('/')}/{directory}/{_slug(assertion.id)}.json"


def assertion_tags(assertion: EngineeringAssertion) -> list[str]:
    """Return explicit retrieval tags useful for inspection/search."""

    tags = [
        f"assertion_id={assertion.id}",
        f"type={assertion.type}",
        f"status={assertion.status}",
        f"importance={assertion.importance}",
    ]

    scope = assertion.scope
    for key, value in (
        ("organization", scope.organization),
        ("domain", scope.domain),
        ("system", scope.system),
        ("repository", scope.repository),
    ):
        if value:
            tags.append(f"{key}={_tag_value(value)}")

    return tags


def _walk_files(client: OpenVikingClient, root: str) -> Any:
    """Yield file entries under ``root`` via level-by-level traversal."""

    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = client.ls(directory)
        except Exception as exc:
            # The live server raises on unreadable directories instead of
            # returning marked entries; skip them without descending.
            if _is_access_denied(exc):
                continue
            raise
        for entry in entries:
            if _entry_access_denied(entry):
                continue
            uri = _entry_uri(entry)
            if uri is None:
                continue
            if isinstance(entry, dict) and entry.get("isDir"):
                stack.append(uri if uri.endswith("/") else uri + "/")
            else:
                yield entry


def _entry_uri(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        uri = entry.get("uri")
        return uri if isinstance(uri, str) else None
    return None


def _entry_access_denied(entry: Any) -> bool:
    return isinstance(entry, dict) and entry.get("access") == "denied"


def _slug(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("\\", "-")
    )


def _tag_value(value: str) -> str:
    return value.strip().lower().replace(" ", "-")
