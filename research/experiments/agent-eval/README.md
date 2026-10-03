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
(`simulated-agent-v1`, top-k 5, evidence budget 5).

| Condition | Available context |
|---|---|
| `repo-only` | Code + repository documentation only |
| `generic-retrieval` | Repository + keyword retrieval over `policies/` |
| `repo-memory` | Same permitted source information via Engineering Assertions + `ContextAssembler`, permission hooks wired |

Fairness note: generic retrieval **does** have access to the exception
document (`policies/legacy-settlement-exception.md`). Otherwise we would
measure missing information rather than the value of structured memory.

## Agent

`simulated_agent` is a fixed deterministic decision procedure (v1),
identical across conditions: HOLD when a repo-specific version pin is
present, PROCEED on an org mandate, ABSTAIN otherwise. Outcome differences
come from the context, not the agent. This is a context-quality evaluation,
not a claim about LLM behavior. Nine runs (3 per condition, seeded
tie-breaking) are a sanity check, not proof of general superiority.

## Permission wiring

The simulated caller is an external agent with no incident access. Before
any context is assembled:

- `authorize`: assertions readable at conclusion level
- `authorize_evidence`: drops `incident://` sources (a restricted
  incident-sourced evidence item is deliberately planted at the highest
  relevance score to verify the boundary)
- `authorize_provenance`: redacts incident provenance entries on assertions
  and evidence (mirrors the retrieval contract's `read_provenance`)

This is the remaining #15 integration requirement: only permitted context
reaches the agent.

## Rubric (predefined, mechanical)

- **R1** recognized the active exception (`M-2027-01` / "remains on Java 17"
  in the rationale)
- **R2** avoided the unauthorized upgrade (decision HOLD, no patch)
- **R3** cited only permitted evidence (no `incident://` citations)

Recorded per run: answer/patch, retrieved URIs, estimated tokens
(chars/4, labeled as estimate), rubric marks, policy violations.

## Results (2026-10-03 sample)

| Condition | Rubric pass |
|---|---|
| repo-only | 0/3 (ABSTAIN — no policy information available) |
| generic-retrieval | 3/3 (HOLD) |
| repo-memory | 3/3 (HOLD) |

The honest reading: on this task, ordinary retrieval with access to the
exception document performs equally well. That is a credible result — it
tells us where repo-memory earns its complexity (deterministic precedence,
permission boundaries, provenance handling) rather than claiming a win the
data does not support. The repo-memory path additionally guarantees the
mandate is suppressed (no contradictory signals) and that restricted
sources never reach the agent; the baseline offers no such guarantees.

## Limitations

- Simulated agent, not an LLM; no agent answer is scored.
- Keyword retrieval stands in for vector search.
- No JDK in this environment: the fixture is a coherent Maven layout,
  verified by structure, not compiled.
- Fixture revision is pinned by content hash (`run.py` records it) plus the
  repo-memory commit SHA in each run report.

## Running

```bash
python research/experiments/agent-eval/run.py
```

Reports land in `runs/` as JSON.
