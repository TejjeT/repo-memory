# Time to Correct Organizational Context: Protocol (Draft)

Issue #33. **Status: DRAFT v0.1 (2026-11-08). Not frozen. Do not collect
trials.** Collection may start only after the open decisions in
[§11](#11-open-decisions-before-freezing) are resolved, this file is frozen
with a commit hash, and its SHA-256 is recorded in the run manifest.

Candidate cases come from [#8's first pass](../../memory-worthiness/candidates.md)
(PR #35). Results of the completed #5 study are summarized in
[docs/status.md](../../../docs/status.md) (PR #34).

---

## 1. Question

#5 showed that when complete permitted context is delivered at task start,
ordinary documents and repo-memory tie on correctness. This protocol asks the
question #5 could not:

> When the relevant engineering context must be **found** in a realistic
> source of truth, **kept current** after a decision changes, or **reused**
> after it was learned once, does repo-memory reduce the time to a verified
> correct decision compared with a well-configured ordinary retrieval path?
> And is any reduction worth its capture, approval and refresh cost?

A tie, or a result favoring ordinary retrieval, is a valid and useful outcome.

### What this protocol can and cannot measure

| Can measure | Cannot measure (state in every report) |
|---|---|
| Agent time and effort to reach a correct, verified decision in one repository at a historical revision | Real organizational waiting (people, approvals, handoffs). None is observed; none will be simulated as if measured. |
| Whether each path surfaces current vs stale guidance inside a real stale window | Cross-team rediscovery. All cases come from one repository with one primary maintainer. |
| Capture and review cost of the memory arm's assertions, measured during this study | The cost of capture at the original time. Assertions are authored retroactively with as-of timestamps. |
| Whether the memory arm wins on cases where it should not (bias check) | General superiority. Small n, one repository, synthetic tasks over real history. |

## 2. Cases

Each case pins a **task revision**: the repository is checked out at that
commit, with all later history removed (§5.3). Correct outcomes are defined
by sources dated before the revision, not by later knowledge.

### Timing cases

| Case | From #8 | Measures | Task revision | Lesson source available at revision | Correct outcome |
|---|---|---|---|---|---|
| **T1** | RM-C1 | Reuse of a lesson | `0d374cb` (2026-10-07 22:40 −04): after the de-hint lesson (`f832f50`), 6 min before the supersession fixture (`73f4c79`) | **Commit messages only** (`f832f50`, `9f131f4`, `de67c73`: "de-hinted fixture"). No file states the rule. | A new frozen fixture for the supersession experiment whose comments, docstrings and names reveal neither the expected change nor stale/current status nor assertion IDs |
| **T2** | RM-C3 | Reuse of a protocol | `5c17afc` (2026-10-07 23:07 −04): supersession fixture merged, before batch collection (`e2fb9c8`) | `research/experiments/agent-eval/README.md` (fresh side chat, `issued_posthoc`) | A collection plan requiring capture-time, prompt-bound receipts **and** worker sessions without experiment history |
| **T3a** | RM-C2 | Freshness inside a stale window | `8dbe325` (2026-10-16): v0 decision recorded, `ROADMAP.md` and `docs/architecture.md` still say SQLite/REST | `docs/v0-scope.md` (current) and `ROADMAP.md` M1, `docs/architecture.md` (stale), with no precedence marker | A storage/transport recommendation for the governed lifecycle (#3) that follows `v0-scope.md` (behind the existing adapter, no new SQLite/REST/vector service) |
| **T3b** | RM-C2 | Freshness after correction | PR #34 merge commit (**TBD**; only if merged before freezing) | Same, with stale documents corrected | Same as T3a |

The supersession experiment's design does not exist yet at `0d374cb`, so the
T1 prompt must supply it: the task (bring the retry configuration into
compliance), the required starting state (gateway retries at 3, a worker-level
retry loop) and the fixture conventions. That wording must itself contain none
of the §8 markers.

T3a vs T3b isolates whether document correction alone closes the gap. If it
does, document hygiene is the adequate answer for this class of case.

### Control cases (memory should not help)

| Case | From #8 | Task revision | Task | Correct outcome |
|---|---|---|---|---|
| **K1** | RM-C4 | `8dbe325` | Add a new relationship field to the provider projection | Patch filters denied IDs for the new field; existing regression tests pass |
| **K2** | RM-C5 | `8dbe325` | Add a stub for a read-only MCP tool | No `mcp` import under `src/repo_memory/`; tool logic in `tools.py`, SDK use in `mcp_server/` |
| **K3** | RM-C6 | `8dbe325` | State the install command that makes the stdio MCP tests runnable | `pip install -e ".[dev]"` (or equivalent that installs the `dev` extra) |

If the memory arm beats ordinary retrieval on the controls by more than the
threshold in §7, treat the protocol as biased and investigate before
interpreting the timing cases.

## 3. Arms

All arms get the same model, settings, task text, output contract, tool
budget and deadline. They differ only in what context is reachable.

| Arm | Reachable context | Role |
|---|---|---|
| **A: ordinary retrieval** | Repository checkout at the task revision, **including full git history up to it**, with file search (`grep`/ripgrep), `git log` / `git log -S` / `git log --grep`, and file reading | Primary baseline. Must be competent: it can find commit-message lessons and every file the memory arm cites. |
| **B: repo-memory** | Arm A **plus** `memory_search` / `memory_get` over the case assertions (§4), served by the repo-memory MCP server with as-of lifecycle state | Treatment |
| **D: curated document** | Arm A **plus** one plain Markdown file containing the same assertion text as Arm B (content, scope, provenance, status), with no lifecycle or precedence semantics | Matched-curation ablation: separates the value of curation from the value of deterministic scope/lifecycle/supersession |
| **C: oracle** | Arm A **plus** the exact source passages that establish the correct outcome, inlined in the task | Diagnostic upper bound only; not a baseline. |

Interpretation:

- **B ≈ A** → ordinary retrieval is adequate.
- **B ≈ D > A** → curation helps, but a small maintained reference document
  is enough; repo-memory's semantics add nothing measurable here.
- **B > D ≥ A**, especially on T3a → deterministic lifecycle/precedence adds
  value beyond curation; this is the only result that supports a narrow
  extension.
- **C ≫ A** but **B ≈ A** → the context matters, but memory did not deliver
  it faster than search did.

## 4. Memory corpus construction

- One assertion per timing case (T1 → RM-C1, T2 → RM-C3, T3 → RM-C2), plus one
  per control (K1–K3), using the schema in `spec/engineering-assertion.schema.json`.
- Each assertion's provenance cites only sources that exist at or before the
  task revision. `created_at` / `effective_from` are set to when the lesson
  was established (e.g. T1: 2026-10-04 15:56 −04).
- T3 additionally includes a superseded assertion for ROADMAP M1
  (`status: superseded`, `superseded_by` the v0 assertion), so lifecycle
  semantics are actually exercised.
- The same text, minus lifecycle fields, becomes Arm D's Markdown file.
- **Retroactive authoring is a stated limitation.** In reality no assertion
  existed at these revisions. The study measures the counterfactual "had it
  been captured when learned", and must count what capturing it costs (§6.3).
- Assertions are authored and frozen **before** any trial. The author records
  wall-clock authoring and review time per assertion.

## 5. Procedure

### 5.1 Resources (proposed; see §11)

- Same model and requested settings for every trial; record whatever model
  identity, settings and token counts the platform exposes.
- Fresh session per trial, without the orchestrating conversation's history.
- Deadline: **600 s** wall clock per trial.
- Tool budget: **40** tool calls per trial (search, read, git, MCP combined).
- Trials: **3 per case per arm** for A, B, D; **1 per case** for C.
  Total: 7 cases × (3 × 3 + 1) = **70 trials** (61 if T3b is dropped).
- Randomized schedule from a recorded seed; trial IDs opaque to workers.

### 5.2 Task text

Each case has one task prompt, identical across arms except for a single
sentence naming the extra reachable context (Arm B: "MCP tools
`memory_search` and `memory_get` are available"; Arm D: "`CONTEXT.md` is
available"; Arm C: inlined passages). Prompts must not mention the lesson,
stale guidance, receipts, hints or the expected answer. Prompts are reviewed
for leading wording before freezing.

### 5.3 Leakage controls

- Each trial gets a fresh clone reset to the task revision, then
  `git reflog expire --all`, removal of all refs except the task branch, and
  `git gc --prune=now`. Verify `git log --all` contains no commit after the
  revision, and record the check output.
- No network access and no GitHub access from inside the trial. Issue and PR
  text is excluded from **all** arms because issue bodies were edited after
  the fact and their historical state cannot be reconstructed.
- `docs/status.md`, `research/memory-worthiness/` and this protocol postdate
  every task revision and are therefore absent from every checkout. Verify.
- **Model-training contamination:** the repository is public. Record that the
  model may have seen later versions. Report if any response cites a fact
  that does not exist at the task revision.
- **Per-trial log paths** for MCP and tool traces (lesson from #27's shared
  log).
- The orchestrator knows the expected outcomes. It must not edit worker
  messages or supply candidate answers.

### 5.4 Evidence

Reuse the established standard: a frozen manifest (source hashes, prompts,
schedule, seed, protocol hash), capture-time, prompt-bound receipts per trial,
raw transcripts and tool traces, and a scoring command that replays from the
saved bundle. Preferably extract a shared receipt/manifest module first
(RM-C3's alternative), so this study does not re-implement it a fifth time.

## 6. Measures

### 6.1 Correctness gate

A trial is **correct** only if it passes its case rubric (§8). Incorrect,
abstained, timed-out, incomplete and harness-failed trials are all
**not correct** and stay in the assigned denominator, reported by category.
Fast wrong answers cannot win.

### 6.2 Primary measure

**Time to verified correct outcome**: wall clock from task delivery to the
final response, for correct trials only. Not-correct trials are censored at
the deadline.

Report per case and per arm:

- correct / assigned
- per-trial times (every trial, with its outcome category)
- median time among correct trials

No significance tests at this n. Report raw per-trial data and say so.

### 6.3 Secondary measures

- Effort: tool calls, files read, git-history queries, MCP calls, bytes
  delivered, and tokens if exposed.
- Source behavior: whether the final answer cites the current source, a stale
  source, or both (T3a/T3b especially). Stale citations are counted even in
  correct answers.
- **Capture and maintenance cost (memory arms):** authoring and review minutes
  per assertion (measured in §4), the number of uses in this study, and
  **amortized cost = (capture + review) ÷ uses**. Also report the refresh
  events the real history would have required (e.g. T3: one supersession on
  2026-10-03), each with an estimated effort marked **estimated**.
- **Freshness window (T3):** the real stale exposure window from history
  (2026-10-03 → PR #34 merge), reported as an observed fact, not a measured
  harm. No incident during the window is known.

### 6.4 Not measured

Organizational waiting time, human handoff delay, cross-team reuse. Any
synthetic delay added in a future variant must be labeled synthetic in every
table.

## 7. Decision thresholds (proposed; freeze before collection)

Aggregate over the timing cases T1, T2 and T3a (9 assigned trials per arm):

1. **Correctness benefit:** Arm B has **at least 3 more correct trials** than
   Arm A.
2. **Time benefit, given equal correctness:** among cases where A and B
   both have ≥2 correct trials, B's median time is **≥30% and ≥60 s lower**
   than A's in at least 2 of the 3 cases.
3. **Net of cost:** the time saved per use, multiplied by a stated plausible
   reuse count, exceeds the measured capture plus review time. The reuse
   count and its justification are frozen with the protocol.
4. **Semantics vs curation:** a benefit is attributed to repo-memory's
   semantics only if B also beats D by threshold 1 or 2. Otherwise it is
   attributed to curation.
5. **Bias check:** if B beats A on K1–K3 by threshold 1 or 2, the timing
   result is reported as inconclusive pending investigation.

Outcomes map to the decision required by #33:

| Result | Decision |
|---|---|
| Neither threshold 1 nor 2 met | Ordinary retrieval is adequate for these cases |
| Met, and B ≈ D | Maintain a small curated reference document; no memory extension |
| Met, B > D, net-of-cost positive | Narrowly justified extension, limited to the semantics that made the difference |
| Bias check fails | Inconclusive; fix the protocol |

## 8. Scoring rubrics

All rubrics are predeclared. Mechanical checks are used wherever possible.

**T1 (fixture).** Output: the complete `fixture/worker.py` and
`fixture/gateway.py`. Checks:

- F1: the supersession scenario's starting state holds (gateway retries
  configured at the stale value; worker-level retry loop present). Checked by
  importing and inspecting, as in the existing supersession rubric.
- F2: no comment, docstring or identifier matches the frozen marker list:
  `stale`, `current polic`, `supersed`, `EA-\d+`, `INC-\d+`, `should be`,
  `will own`, `keep .* disabled`, `deprecated`, `old guidance`
  (case-insensitive).
- Calibration (2026-11-08, scan over comments, docstrings and identifiers):
  the original supersession fixture at `73f4c79` → 4 hits (`stale` ×2,
  `EA-005`, `current polic`); the pre-de-hint retry fixture at `f832f50^` →
  2 hits (`will own`, `keep the gateway layer disabled`); the de-hinted retry
  fixture and the policy-routing fixture → 0 hits. The scanner is to be
  committed with the frozen protocol.
- Known limitation: a marker list catches only listed phrasings. Two human
  reviewers, blinded to arm, also answer "Does any comment reveal the expected
  change?" (yes/no), and agreement is reported. If no human reviewers are
  available, F2 alone scores the case and the limitation is stated.

**T2 (collection plan).** Output: a free-text plan of at most 400 words.
Scored by two human reviewers blinded to arm against two predeclared items:
(a) receipts are issued at collection time and bound to the exact prompt;
(b) workers run without the orchestrating conversation's experiment history.
Both are required. Report agreement and adjudication. **If two human
reviewers are not available, drop T2. Do not model-score it.**

**T3a/T3b (architecture).** Output: JSON
`{"storage": <enum>, "transport": <enum>, "citations": [paths]}` with enums
`storage ∈ {existing-adapter, new-sqlite, new-postgres, new-vector-store, other}`
and `transport ∈ {extend-mcp, new-rest, new-cli, other}`. Correct: `storage =
existing-adapter` and `transport ≠ new-rest`. `citations` is used for §6.3
source behavior, not for correctness. The enum is presented in the same order
in every arm.

**K1–K3.** K1: apply the patch, then run `tests/test_provider_relationships.py`
plus one new frozen test for the new field. K2: AST scan for `mcp` imports
under `src/repo_memory/`. K3: exact-match set of accepted commands.

## 9. Failure handling

- Timeout, abstention, malformed output and protocol violation are not correct
  and stay in the denominator.
- A **harness failure before the worker receives the task** (clone, leakage
  check, server start) may be rerun once, with the original attempt kept and
  labeled. Any failure after task delivery is an outcome, not a rerun.
- No replacement trials and no post-hoc exclusions. Deviations from this
  protocol are listed in the report.

## 10. Threats to validity

- **One repository, one primary maintainer, AI-assisted.** The cases test
  within-project reuse, not organizational discovery. External validity to
  multi-team organizations is low until #8 adds cases from other sources.
- **Selector knowledge.** The cases, tasks and rubrics were designed by
  someone who knows the answers. Mitigation: prompt review for leading
  wording, blinded human scoring for T1/T2, and the control cases.
- **Retroactive memory.** Arm B gets assertions that did not exist at the
  time. This favors B unless capture cost is counted (§6.3, §7.3).
- **Strong baseline by design.** Arm A gets git history. If that makes A tie
  B, that is the answer, not a design flaw.
- **Small n.** 3 trials per cell. Results are descriptive.
- **Contamination.** The model may have seen the public repository's later
  state.
- **Isolation.** Fresh sessions are requested; filesystem isolation per
  trial must be verified, not assumed (see #32's limits).

## 11. Open decisions before freezing

- [ ] Agree the task prompts (T1, T2, T3, K1–K3) and review them for leading
      wording.
- [ ] Confirm deadline (600 s), tool budget (40) and trials per cell (3).
- [ ] Confirm or revise the thresholds in §7, including the reuse count for
      §7.3.
- [ ] Find two human reviewers for T1/T2 scoring, or drop T2 and accept the
      F2-only limitation on T1.
- [ ] Decide on T3b: wait for PR #34 to merge, or drop it.
- [ ] Decide whether to extract a shared receipt/manifest module first
      (§5.4).
- [ ] Decide whether to add cases from sources beyond this repository before
      the first run.
- [ ] Freeze: commit this file, record its hash in the manifest, and change
      the status line to FROZEN.

## 12. Mapping to #33 acceptance criteria

| #33 criterion | Where |
|---|---|
| Link permitted cases and an agreed source-of-truth/effective-time timeline | §2, with timelines in [candidates.md](../../memory-worthiness/candidates.md). Agreement pending (§11). |
| Publish protocol, matched baselines, resources, scoring, deadlines and threshold before running | This file, once frozen |
| Record discovery/update/maintenance measurements with reproducible artifacts and honest isolation limits | §5.4, §6, §10 (at collection) |
| Report timing and correctness together, including negative and failed cases | §6.1–6.2, §9 |
| Choose the simplest adequate approach; a tie is valid | §7 decision table |
