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

## Conditions

Same three-condition protocol as the Java and retry batches:

| Arm | Receives |
|---|---|
| repo-only | `fixture/worker.py`, `fixture/gateway.py`, task text only |
| generic-retrieval | + `corpus/retry-policy-current.md`, `corpus/retry-policy-history.md` |
| repo-memory | + the above, + EA-005/EA-006 via the authenticated MCP read path |

Both retrieval arms get ordinary documents carrying the same underlying
facts. Restricted incident background (INC-463) is withheld in all arms,
including the MCP-delivered context. See `corpus/SOURCES.md`.

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
| S3 single_layer | transient fault retried to success with the gateway layer disabled and unexercised |

`scan_restricted()` scans a serialized MCP response for restricted
markers (`INC-463`, `incident://`); any hit is a leak.

Reference variants under `variants/`: `valid` passes S1/S2/S3,
`invalid_stale` fails all three, `invalid_no_retry` fails S3 only.

## MCP read path

`tests/test_supersession.py` exercises the real MCP dispatcher
(`handle_tool_call`, the same code the stdio server runs):

- `memory_search` returns EA-006 as active guidance; EA-005 (superseded)
  is not in the active set.
- `memory_get("EA-005")` returns it as history with
  `status: "superseded"` and the readable `superseded_by` link.
- `scan_restricted` finds zero markers in search and get responses for
  the permitted caller (doc:// grants; incident:// withheld).

## Next step

After review: collect fresh worker trials in isolated contexts with
identical model/tool/turn limits and capture-time receipts, per the
three-condition protocol. Governed writes (#3) are the following
implementation step, not part of this slice.
