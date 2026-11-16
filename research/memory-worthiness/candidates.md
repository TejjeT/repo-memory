# Candidate Engineering Decisions: First Pass

Issue #8, selected 2026-11-04 from `TejjeT/repo-memory` at `8dbe325` (main,
2026-10-16), plus open PR #34. Guide: [annotation-guide.md](annotation-guide.md) v0.1.

**Reviewers: label each candidate before reading its "Proposed disposition"
section.** Those sections were written by the AI assistant that selected the
candidates. They are not human labels.

Commit links use `https://github.com/TejjeT/repo-memory/commit/<sha>`. Times
are commit or report timestamps. Human effort and waiting time were not
recorded and are **unknown** throughout.

---

## RM-C1: Experiment fixtures must not reveal the expected solution

**Statement.** Frozen experiment fixtures (starting code given to every arm)
must not contain comments or names that reveal the expected change, the
stale-vs-current status of a setting, or assertion IDs. Otherwise the
repository-only arm can infer the answer and the comparison measures the cue,
not the context.

**Scope.** Repository `repo-memory`, component `research/experiments/*`
(every coding-agent experiment fixture).

**Provenance and timeline.**

| When | Event | Source |
|---|---|---|
| 2026-10-04 15:56 −04 | Lesson established: PR #21 review removes "The worker is the layer that will own retry after this task; keep the gateway layer disabled" from the retry fixture ("de-hinted fixture"). | [`f832f50`](https://github.com/TejjeT/repo-memory/commit/f832f508a2318e66bf3033527c96a5bb7e0935ea) |
| 2026-10-07 22:45 −04 | **Missed:** new supersession fixture ships with `# Currently 3 (stale EA-005 guidance …)` and a docstring calling the gateway value "stale guidance". | [`73f4c79`](https://github.com/TejjeT/repo-memory/commit/73f4c791fbe28f88c8451f4b3bdc772b469d6908), `research/experiments/supersession/fixture/worker.py` |
| 2026-10-08 → 10-10 | Two supersession batches tie 3/3 in the repo-only arm. #27 report: repo-only workers inferred the fix "from the fixture's 'stale guidance' comment". | `research/experiments/supersession/trial_mcp/REPORT.md` ([`6399e04`](https://github.com/TejjeT/repo-memory/commit/6399e045a01b98da354c8f709d143a6adf1fcad1)) |
| 2026-10-16 07:31 −04 | **Applied:** policy-routing README states the fixture's "neutral starting policy contain[s] no stale-policy comments, assertion IDs … or expected solution." | [`c49d38d`](https://github.com/TejjeT/repo-memory/commit/c49d38ddfc1f5d06e4d7545f8253160d96487c7e), `research/experiments/policy-routing/README.md` |

**Current vs historical guidance.** No standing rule exists. The lesson
appears in one commit message, one experiment report and one later README.
Nothing earlier prohibited cues.

**Why code alone cannot settle it.** The rule concerns what a fixture should
*not* contain. A new fixture is written from scratch, and no code, test or
lint check encodes the prohibition. The rationale (it invalidates the
repo-only baseline) lives in reports, not code.

**Ordinary-retrieval access.** All sources are in the public repository.
Searching for "hint" or "de-hinted" finds the commit message. Finding the
rationale needs the #27 report. A contributor writing a new fixture has no
obvious prompt to search.

**Costs observed.** One experiment (two batches, 18 trials) where the
repo-only arm was likely contaminated. Both the #26 report ("the fixture's
stale-guidance cue may explain the tie") and the #27 report cite the cue, so
the supersession comparison could not discriminate. Capture cost of a rule: small (one sentence plus
scope). Refresh cost: low; the rule is stable.

**Alternatives.** A fixture-review checklist in `research/benchmark-framework.md`,
or a test that scans fixtures for assertion IDs or words like "stale" and
"current policy". A test catches only known patterns. The lesson is broader.

**Timing data for #33.** Datable learned → missed → applied sequence:
learned 10-04, missed 3 days later, surfaced 10-10, applied 10-16. Effort to
rediscover: unknown.

**Proposed disposition (selector):** moved to
[`selector-dispositions.md`](selector-dispositions.md) so reviewers can read
this file before labelling.

---

## RM-C2: v0 architecture excludes a repo-memory-owned SQLite/REST/vector service

**Statement.** repo-memory is a deterministic contract and policy layer over
a replaceable backend (OpenViking proven). It does not build its own
relational store, REST API or vector index unless a measured need appears.

**Scope.** Repository `repo-memory` (whole project architecture).

**Provenance and timeline.**

| When | Event | Source |
|---|---|---|
| 2026-10-03 00:09 −04 | `ROADMAP.md` added: M1 "Likely stack: SQLite initially … simple REST API". | `0a1b90d` |
| 2026-10-03 15:03 −04 | Decision recorded: `docs/v0-scope.md` (#10, PR #13 verification). | [`3383d1a`](https://github.com/TejjeT/repo-memory/commit/3383d1ad3b789d12a6d5aac257bb6270750cc5c2) |
| 2026-10-03 → 2026-11-04 | **Stale exposure:** `ROADMAP.md` (M1 stack) and `docs/architecture.md` ("SQLite/Postgres", "A relational store is the simplest starting point") continue to describe the superseded design. #3 and #29 both have to restate the decision. | issues #3, #29 |
| 2026-11-04 | Correction proposed in PR #34 (open, not merged as of this writing). | PR #34, `c6875d5` |

**Current vs historical guidance.** Current: `docs/v0-scope.md`. Historical
and superseded, but not marked as such until PR #34: ROADMAP M1,
`docs/architecture.md` "Deployment model".

**Why code alone cannot settle it.** The absence of SQLite in the code is
consistent with both "rejected" and "not built yet". Only the decision record
distinguishes them, and older documents in the same repository say the
opposite.

**Ordinary-retrieval access.** Fully accessible, but search returns both the
current decision and the contradicting older documents with no precedence
signal. This is the supersession/freshness problem in its plainest form.

**Costs observed.** Stale window of at least 32 days and still open. #29 was
filed specifically because "a contributor following the current roadmap can
restart completed work or add infrastructure rejected by the recorded v0
decision." No instance of anyone actually building SQLite/REST is recorded.

**Alternatives.** Fix the documents (PR #34), and mark superseded sections in
place. Once the documents agree, ordinary retrieval is probably adequate.

**Timing data for #33.** Clean approval → propagation case: decision
timestamp, stale-document window and correction timestamp are all datable.
Good candidate for a freshness/propagation measurement. Harm during the window
is unobserved.

**Proposed disposition (selector):** moved to
[`selector-dispositions.md`](selector-dispositions.md) so reviewers can read
this file before labelling.

---

## RM-C3: Trial evidence must be capture-time-bound and collected from history-free workers

**Statement.** A measured coding-agent trial counts as controlled only if each
response is receipt-bound to its exact prompt at collection time (not
posthoc) and workers ran without the orchestrating conversation's experiment
history. Otherwise the batch is exploratory.

**Scope.** Repository `repo-memory`, component `research/experiments/*`
(evaluation protocol).

**Provenance and timeline.**

| When | Event | Source |
|---|---|---|
| 2026-10-04 01:18 −04 | Established: Java "controlled batch" uses a history-free side chat and execution-time receipts. Earlier batches are relabeled exploratory. | [`452979e`](https://github.com/TejjeT/repo-memory/commit/452979e99ffd6b2710e72e69de07effd97ee80f5) (#19), `research/experiments/agent-eval/README.md` |
| 2026-10-05 | Retry runner adds regression tests excluding posthoc receipts. | `b9f774a` |
| 2026-10-08 07:44 −04 | **Missed:** supersession #26 batch collected with workers spawned from a chat containing experiment history (`"blinded": false`). Its receipts are `"binding_type": "posthoc"`. | [`e2fb9c8`](https://github.com/TejjeT/repo-memory/commit/e2fb9c881673246992eb70f0d6ad2ac8d900d22c), `research/experiments/supersession/runs/report.json` |
| 2026-10-09 | PR #26 review: six follow-up commits ("Close PR #26 evidence blockers", "prompt-bound receipts", "strict binding") before merge. Batch reclassified as posthoc/exploratory replay. | `9b72ee2` … `91c3c3c` |
| 2026-10-10, 10-16 | #27 and #32 use capture-time receipts and fresh contexts. | trial reports |

**Current vs historical guidance.** The rule is implemented separately in
each experiment's `run.py` (posthoc/receipt handling appears in four runner
modules) and described in each README. There is no shared module or single
statement of the rule.

**Why code alone cannot settle it.** Each runner enforces its own version.
The fresh-history requirement is an operator procedure that no code checks.
A new experiment starts from a blank runner.

**Ordinary-retrieval access.** Accessible in READMEs and reports, scattered
across four experiments with slightly different terms ("execution-time",
"capture-time", "issued_posthoc", "binding_type").

**Costs observed.** One batch of nine trials collected under the weaker
protocol and downgraded. About six review-fix commits in PR #26, though some
of those added *new* requirements (manifest completeness, prompt binding)
rather than re-learning old ones. Effort hours: unknown.

**Alternatives.** Extract a shared receipt/manifest module so the procedure
is code, not memory. This would likely prevent the receipt half. The
fresh-history half is procedural and cannot be enforced by code.

**Timing data for #33.** Datable established → missed (4 days later) →
corrected sequence. Partial overlap with new requirements makes the "repeated
discovery" share unclear.

**Proposed disposition (selector):** moved to
[`selector-dispositions.md`](selector-dispositions.md) so reviewers can read
this file before labelling.

---

## RM-C4: Denied relationship IDs must be filtered before external provider calls

**Statement.** Before assertions are passed to an external evidence
provider, relationship fields (`superseded_by`, `overrides`, links) must be
stripped of IDs the caller may not see.

**Scope.** Repository `repo-memory`, component `src/repo_memory/context.py`.

**Provenance.** Issue #28 (defect), fixed in
[`91a8b60`](https://github.com/TejjeT/repo-memory/commit/91a8b60) on
2026-10-16 (PR #30). Regression tests in
`tests/test_provider_relationships.py`, for example
`test_authenticated_search_filters_links_before_provider_and_audit`.

**Current vs historical guidance.** Current behavior is the code. Before the
fix, the code leaked. There is no superseded *guidance*, only a fixed bug.

**Why code alone cannot settle it.** It can: the code and regression tests
encode the rule, and a violation fails `pytest`. The *rationale* is in the
issue.

**Ordinary-retrieval access.** Complete: code, tests and issue are linked
from the commit.

**Costs observed.** None after the fix. No reintroduction recorded.

**Alternatives.** Already enforced by tests.

**Timing data for #33.** Not useful. There is nothing to propagate beyond
the merge.

**Proposed disposition (selector):** moved to
[`selector-dispositions.md`](selector-dispositions.md) so reviewers can read
this file before labelling.

---

## RM-C5: The core package must not import MCP or other runtime SDKs

**Statement.** `src/repo_memory/` stays backend-neutral: no web framework,
ORM, database, vector store, LLM SDK, MCP SDK or OpenViking runtime imports.
The MCP SDK is used only under `mcp_server/`.

**Scope.** Repository `repo-memory`, component `src/repo_memory/`.

**Provenance.** `AGENTS.md` "Repository architecture" (loaded by every agent
session via `CLAUDE.md`). `docs/mcp-tools.md` ("Core tool logic lives in
`src/repo_memory/tools.py` with **no MCP imports**"). Applied in PR #24
(`bd80133`, 2026-10-07).

**Current vs historical guidance.** Consistent everywhere. No conflicting
document.

**Why code alone cannot settle it.** Partly true: the code currently
complies, but no test or lint rule fails on a violating import, so the code
shows the state, not the rule.

**Ordinary-retrieval access.** The rule is in the instruction file that
every agent session loads, which is the strongest form of ordinary
retrieval.

**Costs observed.** No violation recorded.

**Alternatives.** Already loaded via `AGENTS.md`. Could be hardened with an
import-boundary test.

**Timing data for #33.** None. Stable since inception.

**Proposed disposition (selector):** moved to
[`selector-dispositions.md`](selector-dispositions.md) so reviewers can read
this file before labelling.

---

## RM-C6: The `dev` extra includes the MCP SDK

**Statement.** `pip install -e ".[dev]"` installs `mcp`, which the stdio
tests and the consumer demo need.

**Scope.** Repository `repo-memory`, file `pyproject.toml`.

**Provenance.** `515ebd1` (2026-10-07, "Add mcp to dev extras for stdio
tests").

**Current vs historical guidance.** `docs/mcp-tools.md` told users to
`pip install mcp` separately with `PYTHONPATH=src` until PR #34 corrected it.
This is a minor stale document.

**Why code alone cannot settle it.** It can: `pyproject.toml` is the
source of truth and is one file read away.

**Ordinary-retrieval access.** Trivial.

**Costs observed.** Negligible. The older instructions still worked.

**Alternatives.** Read `pyproject.toml`.

**Timing data for #33.** Not useful.

**Proposed disposition (selector):** moved to
[`selector-dispositions.md`](selector-dispositions.md) so reviewers can read
this file before labelling.

---

## Summary

The summary table, the selector's proposed dispositions and the implications
for #33 were moved to [`selector-dispositions.md`](selector-dispositions.md)
on 2026-11-16, because they reveal the selector's guesses. Reviewers should
label first and open that file afterwards.
