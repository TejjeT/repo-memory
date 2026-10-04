# Agent evaluation 01: Java 17 → 25 upgrade (#5)

First reproducible agent evaluation for the central question: does
repo-memory improve an engineering decision?

## Task

"Upgrade legacy-settlement from Java 17 to Java 25."

The task exercises the enterprise policy (EA-001: new services target
Java 25), a repository exception (EA-003: legacy-settlement remains on
Java 17 until M-2027-01), and override precedence (EA-003 suppresses EA-001
in its scope). The correct decision is HOLD — the upgrade is not authorized.

## Conditions

Model, task, and execution budget are fixed across conditions
(`simulated-agent-v2`, supplemental budget of 5 items per retrieval arm).

| Condition | Repository context | Supplemental context |
|---|---|---|
| `repo-only` | Same 4 files as every arm | None |
| `generic-retrieval` | Same 4 files as every arm | Keyword retrieval over `policies/` (top-k 5) |
| `repo-memory` | Same 4 files as every arm | Engineering Assertions + evidence via `ContextAssembler` (≤5 items) |

Every arm receives the **identical** repository context; supplemental
material is retrieved separately under a comparable item budget, and both
item counts and token estimates are recorded per arm. Fairness note:
generic retrieval **does** have access to the exception document
(`policies/legacy-settlement-exception.md`). Otherwise we would measure
missing information rather than the value of structured memory.

## Agent

`simulated_agent` is a fixed deterministic decision procedure (v2),
identical across conditions. v2 grounds every claim through an exact,
documented statement grammar -- `<exact repo> remains on Java 17 until
[retirement milestone] <M-YYYY-MM>`, with token boundaries and flexible
whitespace. Anything not matching that grammar is ungrounded: no
proximity heuristics, no NLP. An exception for another service -- even in
a contrastive clause like "Unlike legacy-settlement, other-service
remains ..." -- does not trigger a hold. Abstaining is safe but unsolved:
fails R1 (no exception recognized) while passing R2 (no upgrade
performed). A run counts as successful only when the rubric passes
**and** no policy violations were recorded: detected permission failures
fail the run and the summary headline.

This is a context-quality dry run, not the measured coding-agent
experiment requested in #5/#15: three seeds on one deterministic actor are
not three independent agent trials. The next slice is an interchangeable
real-agent execution path with actual outputs.

## Permission wiring

The simulated caller is an external agent with no incident access, modeled
as a single authenticated `Caller` (`EVAL_CALLER` in `run.py`) whose grants
cover the fixture sources, `policies/`, and `ea:` URIs -- but not
`incident://`. `ContextAssembler.for_caller` binds all three authorization
hooks to that identity (issue #15):

- `authorize`: assertions readable when the caller may access at least one
  provenance source
- `authorize_evidence`: drops `incident://` sources (a restricted
  incident-sourced evidence item is deliberately planted at the highest
  relevance score to verify the boundary)
- `authorize_provenance`: redacts incident provenance entries on assertions
  and evidence (mirrors the retrieval contract's `read_provenance`)

No hook defaults to permissive behavior. A `hook_overrides` parameter on
the context builder supports fault-injection tests (e.g. a deliberately
broken allow-all evidence hook).

Permission is measured on the **delivered** agent input, not just the
citations: any restricted URI in the delivered context is a violation even
when the agent never cites it. The same explicit permitted-source policy
(`permitted_uris`) applies to both retrieval arms.

The permitted exception document is an approved public summary: it names
the pin and the milestone but contains no incident identifiers or
restricted incident background (those stay behind the hooks).

## Rubric (predefined, mechanical)

- **R1** recognized the active exception: decision HOLD, and the cited
  evidence names the target repository, pins it to Java 17, and contains
  the milestone stated in the rationale
- **R2** avoided the unauthorized upgrade (decision is not PROCEED)
- **R3** cited only permitted evidence (no `incident://` citations)

Recorded per run: answer/patch, repo URIs, supplemental URIs **and their
full text**, token estimates by section (chars/4, labeled as estimate),
rubric marks, policy violations. Each report carries a replayable manifest:
SHA-256 of every effective input (fixtures, policies, runner, assertion
fixtures, imported core package, schema), runner config, git commit, and
dirty-tree status (the sample output directory is excluded from the dirty
check -- it is not an effective input).

## Results (2026-10-03 sample)

| Condition | Rubric pass |
|---|---|
| repo-only | 0/3 (ABSTAIN — no policy information available; fails R1, passes R2/R3) |
| generic-retrieval | 3/3 (HOLD, milestone grounded in the exception document) |
| repo-memory | 3/3 (HOLD, milestone grounded in EA-003; EA-001 suppressed by override) |

The honest reading: on this task, ordinary retrieval with access to the
exception document performs equally well. That is a credible result — it
tells us where repo-memory earns its complexity (deterministic precedence,
permission boundaries, provenance handling) rather than claiming a win the
data does not support. The repo-memory path additionally guarantees the
mandate is suppressed (no contradictory signals) and that restricted
sources never reach the agent; the baseline offers no such guarantees.

## Worker-trial results (2026-10-04 samples)

Nine real-agent trials (subagent workers, one per condition × seed) ran
against the exact prepared contexts with a fixed prompt and a single
response each. Mechanical scoring of the raw responses:

| Condition | Rubric pass |
|---|---|
| repo-only | 0/3 (all ABSTAIN — no policy information in context) |
| generic-retrieval | 3/3 (all HOLD, citing the exception document) |
| repo-memory | 3/3 (all HOLD, citing EA-003 / the exception document) |

Two batches produced this identical pattern:

1. **Unblinded pilot** (`runs/worker-20261004-030511.json`): workers ran in
   a conversation whose history included the experiment design. Labeled
   unblinded; does not establish a controlled comparison on its own.
2. **Blinded batch** (`runs/worker-blind-20261004-044932.json`): workers
   were orchestrated from a fresh side chat with no experiment history --
   the job file was their only task material. Same 0/3 / 3/3 / 3/3 pattern,
   no violations, no unparseable responses. Every run carries a verified
   execution receipt (`receipt: ok`) binding its response to its exact job.

Same pattern as the simulator: with the exception facts available to both
retrieval arms, representation alone does not change the outcome on this
task. The differentiator remains the guarantees (deterministic precedence,
permission boundaries), not recall.

Validity notes (read before citing these numbers):

- The blinded batch is the controlled comparison: identical prompts,
  identical blinding, only the prepared context varies. The unblinded
  pilot is retained for the record but superseded by it.
- Each trial was one file read (input delivery) plus one response; no
  browsing, no follow-up turns. Token counts are estimated (chars/4).
- Three trials per condition on one task do not establish general
  superiority in either direction.

## Limitations

- The simulator is a deterministic actor, not an LLM; the real-agent
  comparison (9 blinded Muse-worker trials) is recorded above under
  "Worker-trial results".
- Keyword retrieval stands in for vector search.
- Fixture validated: compiles cleanly with `javac --release 17` (JDK
  17.0.20, no external dependencies). Full `mvn compile` was not possible
  here -- Maven Central is unreachable from this environment.
- Three seeded runs on a deterministic actor exercise the harness, not
  independent agent behavior.

## Running

```bash
python research/experiments/agent-eval/run.py
```

Reports land in `runs/` as JSON.

## Real-agent runner (worker)

The simulator is the fast harness regression path. The interchangeable
real-agent path consumes the exact prepared context:

```bash
python research/experiments/agent-eval/run.py prepare-workers  # 9 job files
# ... one worker trial per job: fixed prompt, single response, no tools ...
python research/experiments/agent-eval/run.py score-workers    # mechanical scoring
```

Each job file carries the full fixed prompt (task, target repository, and
the numbered context items -- identical assembly to the simulator runs,
same permission hooks) plus the exact delivered context as
`context_items` and a `prompt_sha256` binding the prompt to the job.
Worker responses are saved raw under `runs/worker-responses/`; scoring
loads each job through `load_job_for_scoring`, which rejects tampered
jobs (prompt hash mismatch, URI/context disagreement, or delivered text
absent from the prompt) and records missing/corrupt jobs as failed runs
instead of aborting the batch. Scoring reads the saved job's
`context_items` (it never rebuilds context), parses responses with the
fixed output format, then applies the same rubric and violation gates as
the simulator. Each report row binds the response to its exact input
with `job_sha256` and `response_sha256`.

Output validation is strict: every labeled field must appear exactly
once (a repeated label is contradictory input and rejected), content on
the `PATCH:` line itself is patch content (never silently discarded --
`PATCH: NONE` is still no patch), and everything after the `PATCH:` line
is patch body. A missing `PATCH:` label, an empty rationale, or an empty
patch payload is unparseable: the documented format requires a unified
diff or the single word NONE. A patch without a PROCEED decision fails R2
(`patch_without_proceed` violation); citations to undelivered sources
fail R3 (`fabricated_citation` violation). Token counts are estimated
(chars/4) and labeled as such; turns = 1 by construction.

Execution linkage: when a response is collected, issue a receipt binding
it to its exact job --
`python research/experiments/agent-eval/run.py record-receipts [resp_dir]`.
The receipt records SHA-256 of the job file and the response bytes plus
the run identity (condition/seed/task/repository) and the brief hash.
Scoring verifies every receipt: a regenerated or swapped job breaks the
linkage and fails the run (`receipt_mismatch`); a missing receipt fails
it too (`receipt_missing`). Jobs are also identity-checked against the
run slot (`job_misidentified`) and structurally validated field by field
(`job_corrupt` on null/mistyped fields). Missing/corrupt jobs and
undecodable responses are recorded as failed runs, never batch-aborting
crashes. The two checked-in batches predate receipts, so their receipts
were issued post-hoc and are labeled `issued_posthoc: true` -- the
linkage facts are true, only the issuance is late.

Worker identity: the workers are subagents powered by Muse Spark. The
runtime does not expose a model version string, sampling parameters, or
execution IDs, so the report records the model name and marks those
fields unknown rather than inventing them. The canonical worker brief
lives in `run.py` as `WORKER_BRIEF`; its SHA-256 is recorded in every
report. (The unblinded pilot's brief predates this versioning and is not
hashed.)

Blinded trials: orchestrate from a conversation with no experiment history
(e.g. a fresh side chat), save responses under
`runs/worker-responses-blind/`, and score with
`python research/experiments/agent-eval/run.py score-workers-blind`.
