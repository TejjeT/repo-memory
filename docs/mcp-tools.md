# MCP Read Tools: memory_search and memory_get

Issue #4, first slice. Two read-only tools expose the deterministic
engineering context to coding agents over MCP, reusing the core
policy/serialization and #20's authenticated caller boundary. Governed write
tools (`memory_propose` / `memory_supersede`) are a later slice depending on
#3 and are not authorized by adding read tools.

## Tool reference

### memory_search

Search durable engineering memory for a task and target scope.

| Argument | Required | Description |
|---|---|---|
| `task` | yes | What the agent is working on (relevance hint only; never widens authority). |
| `scope` | yes | Target scope object: `organization`, `domain`, `system`, `repository`, `component`, `branch`, `pull_request`. Unknown keys are rejected. |
| `session_token` | yes | Deployment-issued credential, resolved to a verified session server-side. |
| `evidence_budget` | no | Max supporting evidence items (default 10, must be >= 0). |

Returns `assertions` (authorized, active, caller-safe with `redacted` markers
on provenance), `evidence` (bounded, source-authorized), and `conflicts`.
Denied assertions never appear in the output.

### memory_get

Fetch one assertion by ID with caller-safe provenance.

| Argument | Required | Description |
|---|---|---|
| `assertion_id` | yes | The assertion ID. |
| `session_token` | yes | Deployment-issued credential. |

Returns `{"assertion": {...}}`, or `not_found` when the ID does not exist
**or** the caller may not read it -- the two cases are indistinguishable, so
denied assertion existence is never revealed. Lifecycle state (`status`,
`superseded_by`) is returned truthfully; authorization, not lifecycle, is
the security boundary for direct fetch.

## Architecture

```
MCP client -> mcp_server/ (SDK, stdio) -> handle_tool_call
    -> resolve_session (deployment-owned) -> VerifiedSession
    -> authenticate (#20) -> Caller (server-side grants)
    -> assembler_for_session (#20) -> AssembledContext
    -> serialized JSON response
```

- Core tool logic lives in `src/repo_memory/tools.py` with **no MCP imports**.
  The `mcp` SDK is used only under `mcp_server/`.
- Identity comes from the trusted session plus the server-side
  `CallerDirectory`; client-supplied identity/grants are never authorization
  inputs. Missing/invalid credentials fail closed (`unauthenticated`).
- The demo server's token store and directory are clearly-labeled doubles.
  A deployment replaces `resolve_session` with real credential verification
  and `DemoDirectory` with its permission source of record; the tool path is
  unchanged.

## Setup and demo

Prerequisites: Python 3.11+, the repo's venv.

```bash
# from the repo root
.venv/bin/pip install mcp
PYTHONPATH=src .venv/bin/python -m mcp_server        # stdio server
PYTHONPATH=src .venv/bin/python examples/mcp_consumer_demo.py
```

The consumer demo spawns the server over stdio and acts as a coding agent:
alice (broad grants) and bob (narrow grants) search from `billing-api`;
both retrieve the durable cross-repository logging rule (organization
scope), only alice sees the restricted incident rule, denied IDs are
indistinguishable from missing ones, and a bogus token fails closed.

## Trust notes

- Tool relevance cannot widen authority: `task` text guides ranking only.
- Provider output cannot expand the authorized set (assembler boundaries).
- External providers, when configured, are redacted with the request
  caller's own hook inside `assemble` (#20).
- Feedback persistence (recording what agents found useful) needs an
  explicit storage/governance design and is out of scope for this slice.
