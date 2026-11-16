# Roadmap

repo-memory is built in small slices that test the core thesis before adding
infrastructure. Current state, trial results and the detailed next-work order
live in [docs/status.md](docs/status.md). The architectural decision is
[docs/v0-scope.md](docs/v0-scope.md): a deterministic contract and policy layer
over a replaceable backend, **not** a mandatory SQLite/REST/vector service.

## Delivered

| Area | Status | Issues |
|---|---|---|
| Contract: schema, scope hierarchy, provenance, lifecycle states | Done | #1 |
| Permission-aware retrieval contract | Done | #2 |
| Applicability, overrides, supersession, conflict reporting | Done | #11 |
| OpenViking-backed storage path (storage, hierarchy, ACLs, indexing) | Done | #9, #10 |
| Context assembly with budgets and caller-safe evidence | Done | #15 |
| Authenticated callers and external-provider boundary | Done | #20, #28 |
| Read-only MCP tools: `memory_search`, `memory_get` | Done | #4 |
| Bounded coding-agent evaluation (repo only / generic retrieval / repo-memory) | Done; no incremental memory benefit shown; three runs per arm | #5 |
| Governed lifecycle writes with roles and redacted history | Done in-process; OpenViking store is single-writer only | #3 |
| Docs reconciliation | Done | #29 |
| Time-to-correct-context protocol | Drafted, not frozen; sample size under revision | #33 |
| Model-free delivery ablation, calibrated with real supersession rates | Done | #40 |
| External benchmark selection | Recommendation made; release location to confirm | #39 |

## Next, in order

Direction decided 2026-11-11: **research and independent measurement**, not a
competing product, and no patent filing. The plan and its reasons are in #38.

1. **Memory-worthiness labels** (#8) — the candidate sample and a blinded
   labelling packet exist; human labels are pending. Agreement needs a second
   reviewer.
2. **Supersession edge cases** (#41) — decide the broken-chain and
   hidden-successor behavior found by the delivery ablation.
3. **Powered agent study on an external benchmark** (#42) — preregistered,
   with Mneme as an arm. Prior studies indicate 120–200 tasks are needed to
   detect small effects. Model and budget are not yet chosen.
4. **Distractor experiment** (#43) — do agents err when a filtered index
   delivers the governing rule alongside stale or overridden ones?
5. **Access-aware resolution** (#44) — problem statement and prior-art survey.
6. **Time-to-correct-context protocol** (#33) — revise sample size before
   freezing; decide what #42 replaces.

## Deferred

- **Write tools over MCP** (`memory_propose`, `memory_supersede`,
  `memory_feedback`): a separate decision; the server stays read-only.
- **Conditional writes for the OpenViking lifecycle store**: needs backend
  support; single governing writer until then.

## Not planned unless evidence demands it

- Ingestion/extraction from merged PRs, ADRs or incidents; a GitHub review
  workflow for proposed memories.
- A repo-memory-owned REST API, relational metadata store or vector index.
- Graph databases, event buses or distributed deployment.
- Integrations (Backstage, Jira, incident systems, CI/CD, enterprise identity)
  before the core semantics have demonstrated value.

## History

The original milestone plan (M0 contract → M1 local SQLite/REST reference
implementation → M2 MCP → M3 GitHub workflow → M4 permission hierarchy → M5
evaluation → M6 integrations) was exploratory. M0, the permission hierarchy of
M4, the read-only half of M2 and a bounded M5 evaluation were delivered; the
M1 SQLite/REST stack was superseded by the v0 scope decision. See git history
for the original text.
