# Roadmap

repo-memory will be built in small slices that test the core thesis before adding infrastructure.

## M0 — Contract

**Goal:** make the model precise.

Deliverables:

- memory schema
- hierarchy and inheritance rules
- lifecycle semantics
- provenance model
- permission semantics
- retrieval contract
- initial evaluation scenarios

Exit criterion:

A second implementation should be possible from the specification without guessing the intended behavior.

## M1 — Local reference implementation

**Goal:** prove the basic lifecycle.

Capabilities:

- save/propose memory
- approve memory
- get by ID
- search by scope
- semantic recall
- supersede memory
- expire memory
- inspect provenance

Likely stack:

- Python or TypeScript
- SQLite initially
- pluggable embedding provider
- simple REST API

Non-goal:

Do not introduce a graph database, event bus, or distributed architecture unless the prototype demonstrates a need.

## M2 — MCP server

**Goal:** make memory usable by coding agents.

Candidate tools:

- `memory_search`
- `memory_get`
- `memory_propose`
- `memory_supersede`
- `memory_feedback`

Demo:

An agent working on a repository retrieves a migration lesson that cannot be inferred directly from the current source tree.

## M3 — GitHub workflow

**Goal:** turn engineering activity into governed memory.

Experiments:

- suggest memories from merged PRs
- suggest memories from ADR changes
- link memory to commits/issues/PRs
- review proposed memories in GitHub
- invalidate/review memory when evidence changes

Demo:

A merged PR produces a memory proposal; a human approves it; another agent later retrieves it.

## M4 — Permission-aware hierarchy

**Goal:** support organization-scale context safely.

Capabilities:

- org/domain/system/repository scopes
- inheritance
- user/team authorization
- authorization before semantic retrieval
- cross-repository memory relationships

Demo:

Two users asking the same semantic question receive different authorized candidate sets.

## M5 — Evaluation framework

**Goal:** prove that memory improves engineering outcomes.

Candidate metrics:

- task success rate
- retries / failed approaches avoided
- policy violations
- time to correct implementation
- number of repeated discoveries
- context tokens consumed
- precision of retrieved memories
- stale-memory incidents

Evaluation should compare at least:

1. repository alone
2. repository + generic RAG
3. repository + repo-memory

## M6 — Integrations

Potential integrations:

- Backstage/service catalogs
- Jira
- incident systems
- security tooling
- CI/CD
- IDE agents
- enterprise identity

Integrations should be added only after the core memory semantics are stable.

## Near-term issues

The first implementation backlog should focus on:

1. define JSON schema
2. define search/retrieval semantics
3. implement memory lifecycle
4. implement deterministic scope filtering
5. add semantic ranking
6. expose MCP tools
7. create an end-to-end example repository
8. build an evaluation harness
