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
identical across conditions. v2 grounds every claim: it holds only when a
pin for the *target* repository is present in the evidence it actually
received, extracting the milestone from that evidence (never injected by
the actor). An exception written for another service does not trigger a
hold. Abstaining is safe but unsolved: it fails R1 (no exception
recognized) while passing R2 (no upgrade performed).

This is a context-quality dry run, not the measured coding-agent
experiment requested in #5/#15: three seeds on one deterministic actor are
not three independent agent trials. The next slice is an interchangeable
real-agent execution path with actual outputs.

## Permission wiring

The simulated caller is an external agent with no incident access. Before
any context is assembled:

- `authorize`: assertions readable at conclusion level
- `authorize_evidence`: drops `incident://` sources (a restricted
  incident-sourced evidence item is deliberately planted at the highest
  relevance score to verify the boundary)
- `authorize_provenance`: redacts incident provenance entries on assertions
  and evidence (mirrors the retrieval contract's `read_provenance`)

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
fixtures, schema), runner config, git commit, and dirty-tree status.

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

## Limitations

- Simulated agent, not an LLM; the real-agent comparison remains
  outstanding in #5/#15.
- Keyword retrieval stands in for vector search.
- No JDK in this environment: the fixture is a coherent Maven layout,
  verified by structure, not compiled.
- Three seeded runs on a deterministic actor exercise the harness, not
  independent agent behavior.

## Running

```bash
python research/experiments/agent-eval/run.py
```

Reports land in `runs/` as JSON.
