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
| Bounded coding-agent evaluation (repo only / generic retrieval / repo-memory) | Done; no incremental memory benefit shown | #5 |

Read-time lifecycle behavior (state filtering, effective/expiry dates,
supersession, overrides) is delivered. Governed **mutations** are not.

## Next, in order

1. **Docs reconciliation** (#29) — align roadmap, README and experiment
   protocols with delivered work and results.
2. **Candidate cases and memory-worthiness labels** (#8) — 3–5 permitted,
   source-backed candidate decisions first, then a human-labeled sample with
   inter-reviewer agreement. Include cases that favor ordinary retrieval.
3. **Time-to-correct-context protocol** (#33) — preregister a comparison of
   discovery/verification time, update propagation and reuse against a
   well-configured ordinary retrieval path, counting capture, approval and
   refresh costs. Publish the protocol before running another model batch. A
   tie is a valid outcome.
4. **Real-repository pilot** — only once #8 supplies concrete cases.

## Deferred

- **Governed lifecycle** (#3): propose → approve/reject → retrieve, supersede,
  expire/archive with attribution and authorization. Selected only after a
  measured need; first slice is a transition/authorization design.
- **Write tools over MCP** (`memory_propose`, `memory_supersede`,
  `memory_feedback`): follow #3, not before.

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
