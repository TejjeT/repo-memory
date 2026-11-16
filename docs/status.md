# Project Status

Reconciled 2026-11-04 against `main` at `8dbe325` (issue #29); updated
2026-11-16 for work through PR #37. This page is
the single place that says what is implemented, what the trials did and did
not show, and what comes next. Where this page and an older planning document
disagree, this page and [`v0-scope.md`](v0-scope.md) win.

## Architectural decision

[`docs/v0-scope.md`](v0-scope.md) (recorded 2026-10-03, #10 / PR #13) is the
current architectural decision: repo-memory is a **deterministic
engineering-assertion contract and policy layer** with an optional, replaceable
storage backend (OpenViking proven) and a thin read-only transport. It is not a
mandatory SQLite/REST/vector service. Embeddings may only rank candidates after
authorization and scope resolution have fixed the safe set.

The #32 policy-routing result (below) reinforced this: keep the
policy/reference-layer scope; no evidence so far justifies a broader memory
platform.

## Delivered capabilities

| Capability | Code | Docs | Issues |
|---|---|---|---|
| Engineering Assertion schema and loader | `spec/engineering-assertion.schema.json`, `src/repo_memory/models.py`, `loader.py` | [schema-rationale.md](schema-rationale.md), [memory-model.md](memory-model.md) | #1 |
| Permission-aware retrieval contract | `src/repo_memory/policy.py`, `serialization.py` | [retrieval-contract.md](retrieval-contract.md) | #2 |
| Applicability, overrides, supersession, conflicts | `src/repo_memory/policy.py` | [applicability-and-precedence.md](applicability-and-precedence.md) | #11 |
| OpenViking experiment and storage adapter | `src/repo_memory/adapters/openviking.py`, `scripts/openviking_smoke.py` | [openviking-adapter.md](openviking-adapter.md), [v0-scope.md](v0-scope.md) | #9, #10 |
| Context assembly (budgeted, caller-safe evidence) | `src/repo_memory/context.py` | [retrieval-contract.md](retrieval-contract.md) §7–8 | #15 |
| Authenticated callers and external-provider boundary | `src/repo_memory/auth.py`, `context.py` | [authenticated-callers.md](authenticated-callers.md) | #20, #28 |
| Read-only MCP tools (`memory_search`, `memory_get`) | `src/repo_memory/tools.py`, `mcp_server/` | [mcp-tools.md](mcp-tools.md) | #4 |
| Coding-agent evaluation harnesses and trial records | `research/experiments/` | [results below](#trial-results) | #5 |
| Governed lifecycle writes | `src/repo_memory/lifecycle.py`, `OpenVikingLifecycleStore` in `adapters/openviking.py` | [lifecycle.md](lifecycle.md) | #3 |

**Read-time lifecycle and governed writes are both delivered; they are
separate.** Retrieval filters by lifecycle state and
`effective_from`/`expires_at`, honors `superseded_by` and explicit overrides,
and keeps superseded assertions inspectable by ID. Since 2026-11-12 there is
also an in-process write path: propose, approve/reject, supersede, expire and
archive as authorized, attributed operations with caller-safe history. Its
limits: it is not exposed over any transport, the OpenViking-backed store is
safe for a single writer only and was tested against a fake client, and
assertions authored directly as JSON files (for example `examples/payments/`)
bypass it.

## Not implemented (and not planned for v0)

- Write tools over a transport (`memory_propose`, `memory_supersede`,
  feedback). The MCP server is read-only.
- Ingestion/extraction from PRs, ADRs or incidents; a GitHub workflow.
- A standalone memory service, REST API, relational metadata store or vector
  index owned by repo-memory.
- Production identity: the MCP server's tokens, grants and corpus are demo
  doubles (see [mcp-tools.md](mcp-tools.md)).

## Trial results

All batches below are small (three trials per arm), synthetic, single-task
studies. They do not establish general superiority in either direction. At
three runs, a 3/3 result has a 95% interval of roughly 29–100%, so a tie
cannot rule out a real difference and the tasks may simply be at ceiling. Each
original report, receipt and raw response is retained unchanged; follow the
links for full qualifications. "Assigned" denominators count every scheduled
trial, including incomplete ones.

| Batch | Task | Repo only | Generic retrieval | repo-memory | Key qualifiers |
|---|---|---|---|---|---|
| Java upgrade decision ([report](../research/experiments/agent-eval/README.md)) | HOLD vs PROCEED on a policy exception | 0/3 (abstain) | 3/3 | 3/3 | Three batches with the same pattern; the controlled batch used a history-free side chat and capture-time receipts. Earlier two batches are exploratory. |
| Retry/idempotency implementation ([report](../research/experiments/retry-idempotency/README.md)) | Add retry handling | 3/3 | 3/3 | 3/3 | Unblinded. An earlier exploratory batch (2/3, 3/3, 3/3) is preserved with its context-delivery flaws. |
| Supersession replay, #26 ([report](../research/experiments/supersession/runs/report.json)) | Apply current retry policy, reject stale | 3/3 | 3/3 | 3/3 | Posthoc/exploratory replay: receipts attest to saved artifacts, workers shared experiment history, MCP context checked by in-process replay. The fixture's stale-guidance cue may explain the tie. |
| Supersession live MCP transport, #27 ([report](../research/experiments/supersession/trial_mcp/REPORT.md)) | Same task | 3/3 | 3/3 | 2/3 assigned (2/2 completed) | One memory trial (r2) did not complete and is counted as incomplete, not excluded. Isolation is operator-reported; shared transport log prevents per-worker attribution. |
| Policy routing, #32 ([report](../research/experiments/policy-routing/runs/builtin-sol-20261016-01/REPORT.md)) | Cross-repository default/exception routing | 0/3 (three abstentions) | 3/3 | 3/3 | All nine completed. Generic arm is an oracle-document baseline. Abstention is safe but counts as unsolved. |

### Isolation limits common to these batches

- Workers were *requested* as fresh sessions without the orchestrating
  conversation's history. In practice they shared a filesystem and tool
  access; there was no filesystem sandbox or independent access audit.
- Model internals — resolved model version, sampling, hidden turns, tokens and
  cost — were not exposed. Hashes, receipts and process IDs bind saved
  artifacts; they do not prove machine-enforced blinding or model identity.
- The orchestrator knew the expected solution.
- #32 has a separate, operator-driven **post-collection boundary diagnostic**
  (redaction, historical get, private-vs-missing indistinguishability). It is
  not a model trial and is not part of any denominator.

### What each memory arm actually received

The arms were designed to carry equivalent *source facts*, but the exact
delivered representation differed between batches. Do not read the batches as
one protocol.

| Batch | Generic-retrieval arm | repo-memory arm |
|---|---|---|
| Java | Repo files + keyword top-5 over `policies/` (exception document included) | Repo files + four assertions and the permitted exception document as evidence, from `ContextAssembler` (≤5 items) |
| Retry | Fixture + `retry-policy.md`, `idempotency-guide.md` | Fixture + the same documents + EA-002/EA-006 with permitted provenance |
| Supersession #26 | Fixture + `retry-policy-current.md`, `retry-policy-history.md` | Fixture + EA-005/EA-006 as rendered by the in-process MCP dispatcher; **no** ordinary documents |
| Supersession #27 | Same documents as #26, inlined in the brief | Fixture + an MCP client script; the worker fetched EA-005/EA-006 over live stdio MCP; **no** ordinary documents |
| Policy routing #32 | Complete permitted ordinary corpus | The same complete corpus + authenticated live MCP reads |

Restricted incident background was withheld from every arm in every batch.

## What the results do and do not show

**Shown (within these limits):** when the policy facts are absent from the
code, repository-only agents abstained (Java, policy routing). On the retry
and supersession tasks they passed (in supersession, the fixture's
stale-guidance comment may explain this). When the
same facts are supplied as
ordinary documents, agents implement correctly as often as with repo-memory.
No batch demonstrated an incremental correctness benefit from repo-memory over
complete ordinary documents. These are negative/tied results and stay visible.

**Not tested:** the organizational timing hypothesis tracked in **#33** —
whether durable engineering memory reduces the time and effort to *discover
and verify* current, authorized, applicable context, to *propagate*
approvals, revocations and expirations to later decisions, and to *reuse* a
decision across teams and repositories. Every batch above delivered the
context at task start, so none measured discovery delay, update propagation or
amortized reuse. The oracle-document tie does not disprove timing value, and
collection times in the reports include orchestration overhead and are not a
speed comparison.

Any future timing claim must count the cost of capture, approval, refresh,
indexing and permission maintenance, and must compare against a
well-configured ordinary retrieval path rather than a weakened one.

## Model-free evidence since the trials

- **[Delivery ablation](../research/experiments/delivery-ablation/README.md)**
  (synthetic, no model). An ordinary index with access, status, date and
  structural scope filters delivers exactly what the engine delivers without
  its supersession and override links. The links remove distractors; they
  never recover guidance that would otherwise be missing. A "topic tag, newest
  wins" heuristic ties the engine overall and fails differently.
- **[Calibration](../research/experiments/delivery-ablation/calibration/README.md)**
  against Python PEPs, the IETF RFC index and a public ADR dataset. About 10%
  of current documents have a prior revision, not the 60% first assumed, so
  supersession links change the outcome for about 1–4% of queries. Exception,
  complement and restriction rates could not be measured and remain assumed.
- **Two engine gaps** found by the ablation are open decisions in #41: a
  broken supersession chain, and a successor hidden by authorization.
- **Prior work.** [Mneme HQ](../research/open-source/mneme.md) ships
  deterministic decision resolution and enforcement for coding agents within a
  single repository and plans a cross-repository hierarchy. Related published
  results and what remains distinct are in
  [publication-readiness.md](../research/publication-readiness.md) and
  [external-benchmark-selection.md](../research/benchmarks/external-benchmark-selection.md).

## Direction

Decided by the maintainer on 2026-11-11: **research and independent
measurement that is useful to industry**, not a competing product, and no
patent filing. The plan is #38.

## Next work, in order

1. **#28 boundary fix** — done (PR #30).
2. **#5 revised evaluation** — done (PR #32); bounded study closed with a
   tied incremental result.
3. **#29 documentation reconciliation** — done (PR #34; this update).
4. **#3 governed lifecycle** — implemented in-process (PR #37); selected by
   the maintainer on 2026-11-12.
5. **#39 benchmark selection and #40 calibration** — done, pending review.
6. **#8 memory-worthiness labels** — candidate sample and blinded labelling
   packet are ready; human labels are pending. Model-generated labels do not
   count. Reporting agreement needs a second reviewer.
7. **#41 supersession edge cases** — maintainer decision.
8. **#42 powered agent study** on an external benchmark with Mneme as an arm,
   and **#43** distractor experiment. Model and budget not yet chosen.
9. **#44 access-aware resolution** — survey.
10. **#33 timing protocol** — drafted (PR #36), not frozen; revise sample size
    and decide what #42 replaces before any collection.
