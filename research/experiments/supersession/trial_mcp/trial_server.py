"""Trial MCP server for issue #5 supersession worker trials.

Exposes memory_search and memory_get over stdio with the experiment's
assertions (EA-005 superseded, EA-006 current). Uses the real
handle_tool_call dispatcher -- the same code path as the reference
server -- but with trial-scoped demo credentials.

Run:
    python -m trial_mcp.trial_server
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mcp.server.mcpserver import MCPServer

from repo_memory.auth import VerifiedSession
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.tools import handle_tool_call

mcp = MCPServer("repo-memory-trial")

NOW = datetime(2026, 10, 9, tzinfo=UTC)

# Trial demo tokens. NOT production auth.
TRIAL_TOKENS = {
    "trial-agent-token": "trial-agent",
}

# trial-agent gets doc:// only; incident:// is withheld.
TRIAL_GRANTS = {
    "trial-agent": ("doc://",),
}


def _trial_assertions() -> tuple[EngineeringAssertion, ...]:
    scope = Scope(
        organization="Acme", domain="Payments", system="Settlement Platform"
    )
    ea005 = EngineeringAssertion(
        id="EA-005",
        type="constraint",
        content="Gateway retries may be configured up to three attempts.",
        scope=scope,
        status="superseded",
        importance="high",
        provenance=(Provenance(type="document", uri="doc://acme/adr/0029"),),
        created_at=datetime(2025, 8, 1, tzinfo=UTC),
        superseded_by=("EA-006",),
    )
    ea006 = EngineeringAssertion(
        id="EA-006",
        type="incident-derived-constraint",
        content=(
            "Retry must exist at exactly one orchestration layer for "
            "settlement submission; gateway and client retries must not "
            "both be enabled."
        ),
        scope=scope,
        status="approved",
        importance="critical",
        provenance=(
            Provenance(type="incident", uri="incident://INC-463"),
            Provenance(type="document", uri="doc://acme/adr/0041"),
        ),
        created_at=datetime(2026, 6, 12, tzinfo=UTC),
        supersedes=("EA-005",),
    )
    return (ea005, ea006)


class _TrialDirectory:
    def grants_for(self, subject: str) -> tuple[str, ...]:
        return TRIAL_GRANTS.get(subject, ())


def _resolve_session(token: str | None) -> VerifiedSession | None:
    subject = TRIAL_TOKENS.get(token or "")
    if not subject:
        return None
    return VerifiedSession(subject=subject, authenticated_at=NOW, method="trial")


@mcp.tool()
async def memory_search(
    task: str,
    scope: dict[str, Any],
    session_token: str,
    evidence_budget: int = 10,
) -> dict[str, Any]:
    return handle_tool_call(
        "memory_search",
        {
            "task": task,
            "scope": scope,
            "session_token": session_token,
            "evidence_budget": evidence_budget,
        },
        resolve_session=_resolve_session,
        directory=_TrialDirectory(),
        assertions=_trial_assertions(),
    )


@mcp.tool()
async def memory_get(assertion_id: str, session_token: str) -> dict[str, Any]:
    return handle_tool_call(
        "memory_get",
        {"assertion_id": assertion_id, "session_token": session_token},
        resolve_session=_resolve_session,
        directory=_TrialDirectory(),
        assertions=_trial_assertions(),
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
