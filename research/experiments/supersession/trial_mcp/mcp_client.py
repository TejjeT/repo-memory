#!/usr/bin/env python3
"""MCP stdio client for worker trials (issue #5).

Workers invoke this to make ACTUAL MCP transport calls to the repo-memory
MCP server. Uses the MCP SDK's stdio_client (real transport, not a stub).
Every request/response is appended to a transport log -- this log is the
evidence that the worker used live MCP transport.

Usage:
    python mcp_client.py memory_search '{"task": "...", "scope": {...}, "session_token": "..."}'
    python mcp_client.py memory_get '{"assertion_id": "EA-005", "session_token": "..."}'

The transport log goes to MCP_TRANSPORT_LOG (env) or ./mcp-transport.log.
Each entry: {"ts": ..., "direction": "request"|"response", "tool": ..., "payload": {...}}
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
LOG_PATH = Path(os.environ.get("MCP_TRANSPORT_LOG", "./mcp-transport.log"))


def log(direction: str, tool: str, payload: dict) -> None:
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "direction": direction,
        "tool": tool,
        "payload": payload,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


async def _call(tool_name: str, arguments: dict) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # The trial server lives under research/experiments/supersession/;
    # add it to PYTHONPATH for the subprocess.
    trial_pkg_dir = str(Path(__file__).resolve().parents[1])
    env = dict(os.environ)
    env["PYTHONPATH"] = trial_pkg_dir + os.pathsep + env.get("PYTHONPATH", "")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "trial_mcp.trial_server"],
        cwd=str(REPO_ROOT),
        env=env,
    )
    log("request", tool_name, {"arguments": arguments})
    async with stdio_client(params) as (read, write), ClientSession(
        read, write
    ) as session:
        await session.initialize()
        result = await session.call_tool(tool_name, arguments)
        text = result.content[0].text
        try:
            payload = json.loads(text)
        except Exception:
            payload = {"raw_text": text}
        log("response", tool_name, payload)
        return payload


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <tool_name> '<arguments_json>'", file=sys.stderr)
        return 2
    tool_name = argv[1]
    try:
        arguments = json.loads(argv[2])
    except Exception as e:
        print(f"invalid arguments JSON: {e}", file=sys.stderr)
        return 2
    result = asyncio.run(_call(tool_name, arguments))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
