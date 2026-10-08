"""Stdio regression for issue #4's link-filter fix (PR #24 review).

Drives the real MCP server over stdio and asserts caller-safe
relationship filtering end to end: bob reads EA-ORG-LOGGING (which links
to the denied EA-INC-7) and must see an empty conflicts_with, while alice
sees the link preserved.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]


async def _call_tool(session: ClientSession, name: str, arguments: dict) -> dict:
    result = await session.call_tool(name, arguments)
    return json.loads(result.content[0].text)


async def _run() -> dict[str, dict]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server"],
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write), ClientSession(
        read, write
    ) as session:
        await session.initialize()
        scope = {"organization": "Acme", "repository": "billing-api"}
        results = {}
        for subject, token in (("alice", "alice-token"), ("bob", "bob-token")):
            search = await _call_tool(
                session,
                "memory_search",
                {
                    "task": "plan the billing-api deploy",
                    "scope": scope,
                    "session_token": token,
                },
            )
            get = await _call_tool(
                session,
                "memory_get",
                {"assertion_id": "EA-ORG-LOGGING", "session_token": token},
            )
            results[subject] = {"search": search, "get": get}
        return results


def test_stdio_link_filtering_end_to_end():
    results = asyncio.run(_run())

    alice_search = results["alice"]["search"]
    bob_search = results["bob"]["search"]

    alice_logging = next(
        a for a in alice_search["assertions"] if a["id"] == "EA-ORG-LOGGING"
    )
    bob_logging = next(
        a for a in bob_search["assertions"] if a["id"] == "EA-ORG-LOGGING"
    )
    # Alice may read both ends: link preserved.
    assert alice_logging["conflicts_with"] == ["EA-INC-7"]
    # Bob may not read EA-INC-7: link withheld, status retained.
    assert bob_logging["conflicts_with"] == []
    assert bob_logging["status"] == "approved"
    assert "EA-INC-7" not in str(bob_search)

    # Same guarantee through memory_get over stdio.
    assert results["alice"]["get"]["assertion"]["conflicts_with"] == ["EA-INC-7"]
    assert results["bob"]["get"]["assertion"]["conflicts_with"] == []
    assert "EA-INC-7" not in str(results["bob"]["get"])


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
