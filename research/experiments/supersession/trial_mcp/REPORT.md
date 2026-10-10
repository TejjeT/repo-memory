# MCP Transport Trials — Report (supersession-mcp-transport-01)

**Date:** 2026-10-10
**Issue:** #5 (remains open)
**Experiment:** Isolated worker trials using actual MCP transport

## Result

All eight completed trials passed; repo-memory had one incomplete trial.
No MCP advantage demonstrated.

| Condition | Assigned | Completed | Passed |
|-----------|----------|-----------|--------|
| repo-only | 3 | 3 | 3/3 |
| generic-retrieval | 3 | 3 | 3/3 |
| repo-memory | 3 | 2 | 2/2 |

repo-memory-r2 did not complete: the worker analyzed the experiment
instead of performing the task, despite a direct nudge. This incomplete
outcome matters to end-to-end reliability and is not excluded from the
report.

## Method

**Isolation (operator-reported):** Each trial ran in a fresh side chat
created via `chat.create` with `context_mode="fresh"`. Workers received
only the trial brief; no experiment history, prior results, or
methodology notes were present in their context. No machine-verifiable
record of the chat contents is attached; this claim rests on the
operator's procedure.

**MCP transport (repo-memory only):** Workers were instructed to save
`mcp_client.py` and invoke it via subprocess. The client uses the MCP
SDK's `stdio_client` to spawn `trial_mcp.trial_server` and exchange
JSON-RPC messages over stdio — real transport, not pre-rendered JSON.
The trial server exposes `memory_search` and `memory_get` with
EA-005 (superseded) and EA-006 (current); the `trial-agent` token grants
`doc://` only.

**Collection-time receipts (operator-reported):** Eight receipts were
issued immediately on response collection in `trial_mcp/receipts/`.
Each binds the brief SHA-256 to the response SHA-256 with
`binding_type: "capture-time"`. The "immediate" timing is operator
procedure, not a machine-verified timestamp delta; receipt
`captured_at` values are the verifiable record.

## Evidence and qualifications

- **Transport log** (`trial_mcp/mcp-transport.log`): 12 entries
  (6 request/response pairs) showing live `memory_search` and
  `memory_get` calls returning EA-006.
- **Timing:** 4 pairs (03:53:48–03:54:10 UTC) occurred before response
  collection (receipts issued 03:55:17 UTC) and are attributable to the
  trial window. 2 pairs (03:57:20–03:57:28 UTC) occurred after all
  receipts were issued and cannot be attributed to worker task
  performance; they are excluded from trial-window claims.
- **Attribution caveat:** All workers shared `/tmp/mcp-transport.log`,
  so individual calls cannot be attributed to specific workers. EA-006
  references in the repo-memory responses support MCP use (EA-006 does
  not appear in the fixture) but do not establish which calls each
  worker made. Per-worker isolated log paths are needed for the next run.
- **Scoring:** Mechanical check for `GATEWAY_MAX_RETRIES = 0`
  (single retry layer, worker-owned). All eight completed responses
  satisfy this. Run `python run_mcp_trials.py score` to reproduce.

## Interpretation

No MCP advantage demonstrated: repo-only workers (fixture only) also
produced compliant code, inferring the fix from the fixture's "stale
guidance" comment. The repo-memory incomplete trial (r2) is a
reliability signal for the MCP-transport worker protocol, not a scoring
outcome.
