# Project Status

Reconciled 2026-11-04 against `main` at `8dbe325` (issue #29). This page is
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

**Read-time lifecycle is delivered; governed lifecycle mutations are not.**
Retrieval already filters by lifecycle state and `effective_from`/`expires_at`,
honors `superseded_by` and explicit overrides, and keeps superseded assertions
inspectable by ID. What does **not** exist is any write path: propose,
approve/reject, supersede, expire or archive as authorized, attributed
operations. Those remain in deferred issue #3. Assertions today are authored as
JSON files (for example `examples/payments/`).

## Not implemented (and not planned for v0)

- Governed mutations and write tools (`memory_propose`, `memory_supersede`,
  feedback) — deferred, #3.
- Ingestion/extraction from PRs, ADRs or incidents; a GitHub workflow.
- A standalone memory service, REST API, relational metadata store or vector
  index owned by repo-memory.
- Production identity: the MCP server's tokens, grants and corpus are demo
  doubles (see [mcp-tools.md](mcp-tools.md)).

## Trial results

All batches below are small (three trials per arm), synthetic, single-task
studies. They do not establish general superiority in either direction. Each
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

## Next work, in order

1. **#28 boundary fix** — done (PR #30).
2. **#5 revised evaluation** — done (PR #32); bounded study closed with a
   tied incremental result.
3. **#29 documentation reconciliation** — this page.
4. **#8 candidate selection** — identify 3–5 permitted, source-backed cases
   (including ones that favor ordinary retrieval or do not warrant retention),
   then the human-labeled memory-worthiness dataset. Model-generated labels do
   not count as human judgments.
5. **#33 timing protocol** — preregister baselines, resources, scoring,
   deadlines and a practical benefit threshold using #8's cases *before*
   another model batch.
6. **Real-repository pilot** — only once #8 supplies concrete cases.
7. **#3 governed lifecycle** — stays deferred until a measured need selects
   it; first slice is a transition/authorization design, not code.
