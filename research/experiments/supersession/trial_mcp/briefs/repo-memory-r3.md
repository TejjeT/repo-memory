# Trial repo-memory-r3 (supersession-mcp-transport-01)

You are an engineer implementing a change in the payment-worker repository.

TASK: Bring the settlement retry configuration into compliance with current policy (see fixture/worker.py).

## Fixture files

### fixture/worker.py
```python
"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the supersession coding experiment (issue #5).
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: bring the settlement retry configuration into compliance with
current policy. The gateway retry layer is currently enabled at 3
attempts (stale guidance); the worker implements its own retry loop.
"""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer. Currently 3 (stale EA-005 guidance:
# "Gateway retries may be configured up to three attempts").
GATEWAY_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch with worker-level retry (up to 3 tries)."""
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            if attempts >= 2:
                raise
            attempts += 1

```

### fixture/gateway.py
```python
"""Deterministic fake settlement gateway for the retry/idempotency fixture.

Standard library only. The gateway plays a scripted sequence of outcomes
so every run is reproducible; it also models idempotent settlement the way
a real gateway would: the same idempotency key settles at most once, while
a missing key disables deduplication entirely.
"""


class TransientError(Exception):
    """Retryable failure: timeouts, 5xx, connection resets."""


class PermanentError(Exception):
    """Non-retryable failure: invalid account, malformed request."""


class FakeGateway:
    """Scripted gateway. ``script`` is a list of per-call outcomes; each is
    "ok", "transient", "transient_after_settle", or "permanent". Calls
    beyond the script succeed.

    "transient_after_settle" models the ambiguous failure behind the
    idempotency rule: the settlement commits, then the response is lost
    and the client sees a transient error. Retrying with a *different*
    key settles twice; retrying with the *same* key deduplicates.

    ``calls`` records every (batch_id, idempotency_key) received.
    ``settled`` records batch_ids settled exactly once per idempotency key.
    A None key means "no idempotency protection": every successful call
    settles, even repeats.
    """

    def __init__(self, script):
        self._script = list(script)
        self.calls = []
        self.settled = []
        self._seen_keys = set()

    def _commit(self, batch_id, idempotency_key):
        if idempotency_key is None:
            self.settled.append(batch_id)
        elif idempotency_key not in self._seen_keys:
            self._seen_keys.add(idempotency_key)
            self.settled.append(batch_id)

    def submit(self, batch_id, idempotency_key):
        self.calls.append((batch_id, idempotency_key))
        outcome = self._script.pop(0) if self._script else "ok"
        if outcome == "transient":
            raise TransientError("gateway timeout")
        if outcome == "transient_after_settle":
            self._commit(batch_id, idempotency_key)
            raise TransientError("response lost after commit")
        if outcome == "permanent":
            raise PermanentError("invalid account")
        self._commit(batch_id, idempotency_key)
        return {"status": "settled", "batch_id": batch_id}


class GatewayClient:
    """Client-side gateway accessor with an optional built-in retry loop.

    ``max_retries`` bounds the client-side retry loop. ``client_retries``
    counts retries performed inside this client.
    """

    def __init__(self, gateway, max_retries=0):
        self.gateway = gateway
        self.max_retries = max_retries
        self.client_retries = 0

    def submit(self, batch_id, idempotency_key):
        attempts = 0
        while True:
            try:
                return self.gateway.submit(batch_id, idempotency_key)
            except TransientError:
                if attempts >= self.max_retries:
                    raise
                attempts += 1
                self.client_retries += 1

```

## MCP access (actual transport required)

You have a live MCP server with engineering memory. You MUST
query it using the provided client script -- do not guess the
current policy from the fixture alone.

Save the script below as `mcp_client.py`, then run:
```
python mcp_client.py memory_search '{"task": "<your task>", "scope": {"organization": "Acme", "domain": "Payments", "system": "Settlement Platform"}, "session_token": "trial-agent-token"}'
```
Then call `memory_get` for any assertion IDs you need details on.
The client logs all transport to `mcp-transport.log`.

### mcp_client.py
```python
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

```

## Rules
- Implement the task by producing a new version of worker.py.
- Keep the change minimal. Do not restructure unrelated code.
- Follow every constraint in the context. Superseded guidance is
  not current policy; follow the current items.

## Output format
- Respond with the complete, self-contained new worker.py.
- You may wrap it in a single ```python fenced block.
- Brief code comments are welcome. No explanations outside the code.