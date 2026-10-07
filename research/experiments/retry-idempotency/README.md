# Retry/Idempotency Coding Experiment (issue #5)

## Objective

The Java decision task tied between generic retrieval and repo-memory
(0/3, 3/3, 3/3). This experiment tests whether memory changes
**implementation correctness**: can the agent write a correct retry
implementation, not just pick the correct decision?

## Task

> Add retry handling for transient settlement submission failures in
> `settle_batch` (see `fixture/worker.py`).

The durable constraints (from EA-002/EA-006):

- **Idempotency**: the idempotency key is generated once per batch and
  reused across every retry boundary (gateway, queue, worker).
- **Single retry layer**: retry exists at exactly one orchestration
  layer; the worker owns it here, so the gateway/client layer stays
  disabled.

## Conditions

Same three-condition protocol as the Java batch:

| Arm | Receives |
|---|---|
| repo-only | `fixture/worker.py`, `fixture/gateway.py`, task text only |
| generic-retrieval | + `corpus/retry-policy.md`, `corpus/idempotency-guide.md` |
| repo-memory | + the above, + EA-002/EA-006 assertions with permitted provenance |

Both retrieval arms get ordinary documents carrying the same underlying
facts as EA-002/EA-006. Restricted incident background (INC-412,
INC-463, ADR-37/41) is withheld in all arms. See `corpus/SOURCES.md`.

## Fixture

`fixture/` holds the frozen starting code: a minimal payment worker
(`worker.py`, no retry handling) plus a deterministic scripted
`FakeGateway` (`gateway.py`). Standard library only, offline, no real
payments. `REVISION` records the language/runtime and SHA-256 of both
files; the test suite fails if they change without a revision update.

The gateway models the ambiguous failure behind the idempotency rule:
`transient_after_settle` commits the settlement, then the response is
lost. Retrying with the same key deduplicates; a regenerated or missing
key settles twice.

## Evaluator (no LLM)

`evaluator/rubric.py` applies one candidate `worker.py` to an isolated
copy of the frozen fixture, then runs scripted scenarios in a
subprocess (30s timeout guards against runaway retry loops):

| Check | Scenario | Pass condition |
|---|---|---|
| R1 key_stable | transient, ok; two-batch (A, B) | same non-null key on every attempt; the submitted key is the caller-provided key (not regenerated or hardcoded); caller keys do not leak across batches; every batch completes cleanly (settled response returned, no exception) |
| R2 no_duplicate | transient_after_settle, ok | batch settled exactly once |
| R3 transient_retried | transient x2, ok | succeeds on the 3rd call |
| R4 permanent_stops | permanent | PermanentError, exactly 1 call |
| R5 single_retry_layer | transient, ok | client max_retries == 0 and no client retries |

### How diffs are applied and scored

A candidate implementation is a complete `worker.py` replacement
(what a worker trial produces). The evaluator:

1. copies `fixture/gateway.py` + the candidate into a fresh temp dir,
2. runs a fixed driver there per scenario (subprocess; the driver writes
   its scenario record to a dedicated `result.json`, candidate stdout is
   captured separately and never parsed),
3. scores R1..R5 as pure predicates over recorded gateway calls.

No LLM reads the diff, judges style, or makes policy decisions. The
unified diff of a candidate vs the frozen `worker.py` is a report
artifact, computed with `difflib`, not an input to scoring.

## Evaluator discrimination

`variants/` holds reference solutions plus seven known-invalid variants.
The suite (`tests/test_retry_idempotency.py`) proves the evaluator
tells them apart:

| Variant | Result |
|---|---|
| reference (worker retry, stable key, gateway layer off) | 5/5 pass |
| reference-logging (reference + print to stdout) | 5/5 pass (result protocol is stdout-separated) |
| invalid-regenerated-key (fresh UUID per attempt) | R1, R2 fail |
| invalid-duplicate-layer (worker loop + gateway retries on) | R5 fails |
| invalid-unsafe-resubmit (retries with key=None) | R1, R2 fail |
| invalid-swallowed-ambiguous (returns None on response-lost) | R2 fails (settlement count right, no settled response) |
| invalid-raise-on-success (PermanentError after successful submit) | R1, R2, R3 fail |
| invalid-hardcoded-key (literal "key-1", ignores caller key) | R1 fails (two-batch scenario) |
| invalid-none-second-batch (returns None for batch-B) | R1 fails (per-batch completion) |

Every invalid variant imports cleanly; all but `invalid-raise-on-success`
settle the happy path (`invalid-raise-on-success` intentionally raises
after a successful submit, so it fails the happy path by design) --
compilation and test success alone do not pass the rubric. The driver
reports through `result.json`, never stdout, so candidate debug output
cannot corrupt scoring; a missing/malformed result is a recorded harness
failure. Every retryable scenario (clean, transient, ambiguous, multi)
must return the gateway's settled response with no exception, and two
distinct batches on one gateway must settle under their own caller keys.

## Recorded worker trials

The fixture/evaluator from #21 is reused by `run.py` to prepare nine
prompt-bound jobs, record response receipts, extract complete workers,
and mechanically score three trials per condition. Run `python run.py --help`
from this directory for preparation, receipt and scoring commands.

`runs/worker-fresh-20261005-222944.json` records **3/3, 3/3, 3/3**:
all arms passed all five checks. This task provides no evidence that
repo-memory improves correctness over ordinary retrieval or repository
context alone. Workers inherited an orchestrating conversation containing
experiment history, so this batch is explicitly `blinded: false`.
Unknown model/sampling/execution details remain unknown.

The scorer validates the actual delivered URI sequence, nonempty document
text, declared context lists and withheld incident identifiers. Invalid
jobs, missing/mismatched receipts and posthoc receipts cannot count as
capture-time successes. Receipts bind saved artifacts; they do not
independently audit worker execution.

`runs/exploratory-batch-01/` preserves the original 2/3, 3/3, 3/3 batch
unchanged, including its documented context-delivery flaws. Original
reports retain the input hashes and scorer version used at scoring time.
Tightening validation does not require rewriting collection artifacts.

## Validity notes

- The fixture is synthetic and small by design; it exercises the two
  rules, not production payment logic.
- Three trials per condition on one task cannot establish general
  superiority; equal or negative results are valid outcomes.
- The starting `worker.py` exposes `GATEWAY_MAX_RETRIES` as config
  surface but states no rationale. Ordinary gateway API documentation
  explains the idempotent behavior (same key deduplicates); what the
  repository alone does not explain is the organization-specific
  retry-ownership rationale -- the key must survive retry boundaries as
  a standing rule, and retry must live at exactly one orchestration
  layer.
