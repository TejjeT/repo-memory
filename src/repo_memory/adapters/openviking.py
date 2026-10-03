"""OpenViking adapter for Engineering Assertions.

The adapter depends on a tiny client protocol instead of importing OpenViking's
SDK directly. Any compatible SyncHTTPClient can be injected at runtime.

OpenViking is used for shared resource storage, ACL enforcement, and indexing.
repo-memory remains responsible for engineering applicability and lifecycle
semantics.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

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

# Exception class names that signal an authorization denial from an OpenViking
# server. Matched by name so this adapter does not need to import the SDK.
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
