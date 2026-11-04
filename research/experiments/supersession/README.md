# Supersession Coding Experiment (issue #5)

## Objective

The retry/idempotency batch tied across all three conditions (3/3, 3/3,
3/3). This experiment tests two narrower questions with the authenticated
MCP read path now available:

1. **Supersession**: does the agent follow current guidance (EA-006) and
   reject stale guidance (EA-005)?
2. **Restricted provenance**: do permitted conclusions stay usable while
   restricted identifiers never enter delivered context or citations?

Ties remain valid outcomes -- the existing results have not established
an advantage over ordinary retrieval.

## Task

> Bring the settlement retry configuration into compliance with current
> policy (see `fixture/worker.py`).

The frozen fixture has the worker retrying at its own layer while the
gateway retry layer sits at 3 attempts (the stale EA-005 value). Current
policy (EA-006) requires exactly one retry layer, worker-owned, so the
correct change is `GATEWAY_MAX_RETRIES = 0`. Keeping 3 follows the
superseded guidance; removing the worker loop leaves zero layers.

## Status

Complete (2026-10-10). Two batches were collected; both are retained with
their original reports. Neither demonstrated an advantage for repo-memory.
Project-level results and next work: [docs/status.md](../../../docs/status.md).

| Batch | Evidence | Repo only | Generic retrieval | repo-memory |
|---|---|---|---|---|
| #26 replay ([runs/report.json](runs/report.json)) | Posthoc/exploratory | 3/3 | 3/3 | 3/3 |
| #27 live transport ([trial_mcp/REPORT.md](trial_mcp/REPORT.md)) | Capture-time receipts, operator-reported isolation | 3/3 | 3/3 | 2/3 assigned (r2 incomplete) |

The #26 replay scored saved responses with the current evaluator; receipts
were bound posthoc to saved artifacts, workers shared experiment history, and
MCP context was checked through an in-process dispatcher replay. The
fixture's stale-guidance comment lets repo-only workers infer the fix, which
may explain the tie in both batches.

## Conditions

The two batches used **different delivery protocols**. All arms in both
batches carry the same underlying source facts, but not the same
representation. Restricted incident background (INC-463) is withheld in all
arms, including MCP-delivered context. See `corpus/SOURCES.md`.

### #26 replay (`run.py`)

| Arm | Receives |
|---|---|
| repo-only | `fixture/worker.py`, `fixture/gateway.py`, task text only |
| generic-retrieval | Fixture + `corpus/retry-policy-current.md`, `corpus/retry-policy-history.md` |
| repo-memory | Fixture + EA-005/EA-006 as rendered by the authenticated MCP dispatcher (`handle_tool_call`), in-process; **no** ordinary documents |

### #27 live transport (`trial_mcp/`)

| Arm | Receives |
|---|---|
| repo-only | Brief with fixture files and task text |
| generic-retrieval | Brief with fixture + both corpus documents inlined |
| repo-memory | Brief with fixture + `mcp_client.py`; the worker fetches EA-005/EA-006 itself over stdio MCP from `trial_mcp.trial_server`; **no** ordinary documents |

Exact briefs and manifests are in `trial_mcp/briefs/`.

## Fixture

`fixture/` holds the frozen starting code: `gateway.py` (deterministic
scripted `FakeGateway`, copied from the retry experiment) and `worker.py`
(worker-level retry loop, gateway at the stale value 3). Standard library
only, offline. `REVISION` records the language/runtime and SHA-256 of
both files.

## Evaluator (no LLM)

`evaluator/rubric.py` applies one candidate `worker.py` to an isolated
copy of the frozen fixture, then runs scripted scenarios in a subprocess
(30s timeout). Checks are predeclared:

| Check | Pass condition |
|---|---|
| S1 current_compliance | gateway `max_retries == 0` |
| S2 stale_rejected | gateway `max_retries != 3` (the EA-005 value) |
| S3 single_layer | the two transient failures are retried with the same batch and key, followed by exactly one settlement and the expected successful response; gateway retries remain disabled and unexercised |

Harness soundness (deterministic driver observations):

- `result.json` is deleted before each scenario; a driver that crashes
  without writing yields a harness error, never a stale pass.
- Non-zero driver exits are rejected even if a result file exists (a
  worker cannot forge a passing result and die).
- Malformed result shapes are harness findings, not evaluator crashes.
- The gateway call trace must contain exactly three submissions of B1
  with key-1; the settlement trace must contain only B1, and the worker
  must return the gateway's successful response for B1. Regressions cover
  wrong responses, changed request identities, and extra settlements.

`scan_restricted()` scans a serialized MCP response for restricted
markers (`INC-463`, `incident://`); any hit is a leak.

Reference variants under `variants/`: `valid` passes S1/S2/S3;
`invalid_stale` fails all three; `invalid_no_retry` fails S3 only;
`invalid_never_submits`, `invalid_swallow`, `invalid_crash`, and
`invalid_forge` are adversarial regressions for the harness checks.

## MCP read path

`tests/test_supersession.py` exercises the real MCP dispatcher
(`handle_tool_call`, the same code the stdio server runs):

- `memory_search` returns EA-006 as active guidance; EA-005 (superseded)
  is not in the active set.
- `memory_get("EA-005")` returns it as history with
  `status: "superseded"` and the readable `superseded_by` link.
- `scan_restricted` finds zero markers in search and get responses for
  the permitted caller (doc:// grants; incident:// withheld).

## Follow-on work

Trials for this experiment are complete. The bounded #5 study concluded with
the policy-routing batch ([report](../policy-routing/runs/builtin-sol-20261016-01/REPORT.md)).
Next project work is candidate selection (#8) and the time-to-correct-context
protocol (#33); governed writes (#3) remain deferred. See
[docs/status.md](../../../docs/status.md).
