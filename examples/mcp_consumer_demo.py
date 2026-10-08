"""Agent-consumer demo for issue #4's MCP tools.

Spawns the reference MCP server over stdio and acts as a coding agent:

1. As alice (broad grants) and bob (narrow grants), search memory for a
   deploy task in the billing-api repository. Both retrieve the durable
   cross-repository logging rule (org scope); only alice sees the
   restricted incident rule, and bob's provenance is redacted.
2. Fetch one assertion by ID with memory_get, including a denied ID that
   must look identical to a missing one.
3. Show that a missing credential fails closed.

Run:  python examples/mcp_consumer_demo.py
Requires: pip install mcp
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_MODULE = "mcp_server"


async def call_tool(
    session: ClientSession, name: str, arguments: dict
) -> dict:
    result = await session.call_tool(name, arguments)
    # FastMCP returns content blocks; the payload is JSON text.
    text = result.content[0].text
    return json.loads(text)


def summarize_search(label: str, payload: dict) -> None:
    print(f"== {label} ==")
    for assertion in payload["assertions"]:
        redacted = [
            p["uri"] for p in assertion["provenance"] if p["redacted"]
        ]
        print(
            f"  {assertion['id']}: redacted={redacted or False}"
            f" rationale={'withheld' if assertion['rationale'] is None else 'present'}"
        )
    print()


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", SERVER_MODULE],
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write), ClientSession(
        read, write
    ) as session:
        await session.initialize()

        scope = {"organization": "Acme", "repository": "billing-api"}

        alice = await call_tool(
            session,
            "memory_search",
            {
                "task": "plan the billing-api deploy",
                "scope": scope,
                "session_token": "alice-token",
            },
        )
        summarize_search("alice search (billing-api)", alice)

        bob = await call_tool(
            session,
            "memory_search",
            {
                "task": "plan the billing-api deploy",
                "scope": scope,
                "session_token": "bob-token",
            },
        )
        summarize_search("bob search (billing-api)", bob)

        alice_ids = [a["id"] for a in alice["assertions"]]
        bob_ids = [a["id"] for a in bob["assertions"]]
        # The cross-repository rule reaches both agents.
        assert "EA-ORG-LOGGING" in alice_ids and "EA-ORG-LOGGING" in bob_ids
        # The restricted incident rule reaches only alice.
        assert "EA-INC-7" in alice_ids and "EA-INC-7" not in bob_ids

        # Relationship links are caller-safe: alice sees the
        # EA-ORG-LOGGING -> EA-INC-7 conflict link; bob's is withheld.
        alice_logging = next(
            a for a in alice["assertions"] if a["id"] == "EA-ORG-LOGGING"
        )
        bob_logging = next(
            a for a in bob["assertions"] if a["id"] == "EA-ORG-LOGGING"
        )
        assert alice_logging["conflicts_with"] == ["EA-INC-7"]
        assert bob_logging["conflicts_with"] == []
        print("link filtering over stdio: alice sees link, bob does not")

        # memory_get: permitted fetch with caller-safe provenance.
        fetched = await call_tool(
            session,
            "memory_get",
            {"assertion_id": "EA-INC-7", "session_token": "alice-token"},
        )
        assert fetched["assertion"]["id"] == "EA-INC-7"
        print("alice memory_get EA-INC-7: ok")

        # memory_get: denied ID is indistinguishable from missing.
        denied = await call_tool(
            session,
            "memory_get",
            {"assertion_id": "EA-INC-7", "session_token": "bob-token"},
        )
        missing = await call_tool(
            session,
            "memory_get",
            {"assertion_id": "EA-NOPE", "session_token": "bob-token"},
        )
        assert denied == missing == {
            "error": {
                "code": "not_found",
                "message": "assertion not found or not accessible",
            }
        }
        print("bob memory_get EA-INC-7 == missing ID: identical not_found")

        # Missing credential fails closed.
        no_auth = await call_tool(
            session,
            "memory_search",
            {
                "task": "plan the billing-api deploy",
                "scope": scope,
                "session_token": "bogus-token",
            },
        )
        assert no_auth["error"]["code"] == "unauthenticated"
        print("bogus token: unauthenticated, fail closed")

    print("OK: consumer demo passed.")


if __name__ == "__main__":
    asyncio.run(main())
