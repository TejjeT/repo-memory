"""Reference MCP server exposing memory_search and memory_get (issue #4).

Stdio transport. The ``mcp`` SDK is imported only here -- the core package
(``src/repo_memory/``) has no MCP/framework dependencies.

Credential verification is deployment-owned: this reference server resolves
a demo ``session_token`` to a ``VerifiedSession`` through ``DemoSessionStore``.
That store is a clearly-labeled double, NOT production authentication. A real
deployment replaces it with its own session/OIDC/API-key verification and
keeps everything else.

Run:
    python -m mcp_server
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mcp.server.mcpserver import MCPServer

from repo_memory.auth import VerifiedSession
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.tools import TOOL_DEFINITIONS, handle_tool_call

mcp = MCPServer("repo-memory")

NOW = datetime(2026, 10, 7, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Demo doubles (NOT production infrastructure).
# ---------------------------------------------------------------------------

#: Demo token -> subject. A deployment replaces this with real credential
#: verification (session store, OIDC, API keys).
DEMO_TOKENS = {
    "alice-token": "alice",
    "bob-token": "bob",
}

#: Demo subject -> source grants. A deployment backs this with its real
#: permission source of record.
DEMO_GRANTS = {
    "alice": ("doc://", "incident://"),
    "bob": ("doc://",),
}


def resolve_session(token: str | None) -> VerifiedSession | None:
    """Map a demo session token to a verified session (None when unknown)."""
    if not token or token not in DEMO_TOKENS:
        return None
    return VerifiedSession(
        subject=DEMO_TOKENS[token], authenticated_at=NOW, method="demo-token"
    )


class DemoDirectory:
    """Demo caller directory: subject -> grants from DEMO_GRANTS."""

    def grants_for(self, subject: str) -> tuple[str, ...]:
        return DEMO_GRANTS[subject]


def demo_corpus() -> tuple[EngineeringAssertion, ...]:
    """Small demo corpus with a durable cross-repository rule.

    EA-ORG-LOGGING applies at organization scope, so an agent working in any
    repository retrieves it -- the cross-repository case from #4.
    """
    return (
        EngineeringAssertion(
            id="EA-ORG-LOGGING",
            type="constraint",
            content="All services must emit structured JSON logs with trace ids.",
            scope=Scope(organization="Acme"),
            status="approved",
            importance="high",
            provenance=(
                Provenance(type="document", uri="doc://handbook/logging"),
            ),
            created_at=NOW,
            rationale="Adopted org-wide to make cross-service tracing possible.",
            # Link to a restricted assertion: exercises caller-safe
            # relationship filtering over the stdio transport.
            conflicts_with=("EA-INC-7",),
        ),
        EngineeringAssertion(
            id="EA-PAY-RETRY",
            type="constraint",
            content="Payment workers retry at most once, at the worker layer.",
            scope=Scope(organization="Acme", domain="Payments"),
            status="approved",
            importance="critical",
            provenance=(
                Provenance(type="document", uri="doc://handbook/retry"),
            ),
            created_at=NOW,
        ),
        EngineeringAssertion(
            id="EA-INC-7",
            type="incident-derived-constraint",
            content="Freeze deploys during incident INC-7 review.",
            scope=Scope(organization="Acme"),
            status="approved",
            importance="critical",
            provenance=(
                Provenance(
                    type="incident",
                    uri="incident://restricted/7",
                    revision="rev-9",
                    access_policy_ref="incident-access",
                ),
            ),
            created_at=NOW,
            rationale="Incident 7 postmortem action item; details restricted.",
        ),
    )


_DIRECTORY = DemoDirectory()
_CORPUS = demo_corpus()


# ---------------------------------------------------------------------------
# Tool wiring: MCP arguments -> core tools.
# ---------------------------------------------------------------------------


@mcp.tool(
    name="memory_search",
    description=TOOL_DEFINITIONS[0]["description"],
)
def memory_search(
    task: str,
    scope: dict[str, Any],
    session_token: str,
    evidence_budget: int = 10,
) -> dict[str, Any]:
    """Search durable engineering memory for the caller's task and scope."""
    return handle_tool_call(
        "memory_search",
        {
            "task": task,
            "scope": scope,
            "session_token": session_token,
            "evidence_budget": evidence_budget,
        },
        resolve_session=resolve_session,
        directory=_DIRECTORY,
        assertions=_CORPUS,
    )


@mcp.tool(
    name="memory_get",
    description=TOOL_DEFINITIONS[1]["description"],
)
def memory_get(assertion_id: str, session_token: str) -> dict[str, Any]:
    """Fetch one engineering assertion by ID with caller-safe provenance."""
    return handle_tool_call(
        "memory_get",
        {"assertion_id": assertion_id, "session_token": session_token},
        resolve_session=resolve_session,
        directory=_DIRECTORY,
        assertions=_CORPUS,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
