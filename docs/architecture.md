# Architecture

## Goal

repo-memory provides durable engineering memory that can be retrieved by humans and AI agents without forcing every tool to implement its own memory subsystem.

The architecture deliberately separates **sources of truth** from **durable learned context**.

> **Reading this document.** Most of this page describes the *conceptual
> target*: ingestion, a memory service with mutations, multiple transports.
> Only part of it is implemented. The section
> [Implemented reference paths](#implemented-reference-paths) lists what exists
> today; [v0-scope.md](v0-scope.md) is the binding architectural decision and
> [status.md](status.md) tracks delivered work and results.

## Implemented reference paths

```text
hand-authored JSON assertions (examples/, spec/ schema)
        │  loader.py
        ▼
EngineeringAssertion models ──► optional OpenViking adapter (storage, ACLs, indexing)
        │
        ▼
auth.py: VerifiedSession → Caller (server-side grants)
        │
        ▼
policy.py: authorization → lifecycle/effective dates → scope/applicability
           → supersession → explicit overrides → conflict reporting
        │
        ▼
context.py: budgeted assembly, provider boundary, provenance redaction
        │  serialization.py
        ▼
tools.py: memory_search / memory_get (read-only)
        │
        ▼
mcp_server/: stdio MCP server with demo identities and corpus
```

| Conceptual component | Implemented today | Not implemented |
|---|---|---|
| Memory sources / ingestion | JSON files validated against the schema | Extraction, normalization, dedupe, GitHub/ADR/incident ingestion |
| Memory service — lifecycle | Read-time filtering by state, effective/expiry dates, supersession, overrides | Propose, approve/reject, supersede, expire, archive as governed writes (#3) |
| Policy engine | Read authorization (discover/content) for authenticated callers | Authorization of propose/approve/supersede transitions |
| Metadata store | In-memory models; OpenViking adapter as optional backend | A repo-memory-owned relational store |
| Semantic index | Pluggable `EvidenceProvider` (retrieval assist) that ranks evidence only after the safe candidate set is fixed; OpenViking supplies indexing | A repo-memory-owned vector index |
| Retrieval / context API | `ContextAssembler`, `memory_search`, `memory_get` | Feedback, audit history API |
| Transports | Read-only stdio MCP server | REST API, CLI, MCP write tools |

Ingestion, mutations and additional transports are added only when a measured
consumer need selects them.

## Conceptual target architecture

```text
                    ┌──────────────────────────────┐
                    │        Memory Sources        │
                    │                              │
                    │ Humans  Agents  GitHub  CI   │
                    │ ADRs  Incidents  Catalogs    │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │   Ingestion / Proposal│
                       │                       │
                       │ extract • normalize   │
                       │ validate • dedupe     │
                       └───────────┬───────────┘
                                   │
                                   ▼
                      ┌────────────────────────┐
                      │     Memory Service     │
                      │                        │
                      │ lifecycle              │
                      │ scope                  │
                      │ provenance             │
                      │ permissions            │
                      │ supersession           │
                      │ review                 │
                      └──────────┬─────────────┘
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
          ┌─────────────────┐         ┌──────────────────┐
          │ Metadata Store  │         │ Semantic Index   │
          │                 │         │                  │
          │ identity        │         │ relevance        │
          │ relationships   │         │ similarity       │
          │ permissions     │         │ recall           │
          └────────┬────────┘         └─────────┬────────┘
                   └─────────────┬──────────────┘
                                 ▼
                      ┌────────────────────────┐
                      │ Retrieval / Context API│
                      └──────────┬─────────────┘
                                 │
              ┌──────────────────┼───────────────────┐
              ▼                  ▼                   ▼
          REST API            MCP Server             CLI
              │                  │                   │
              ▼                  ▼                   ▼
        Internal tools      Coding agents         Developers
```

## Key architectural decision: hybrid retrieval

A repository-memory system should not rely solely on vector search.

Retrieval should happen in roughly this order:

1. establish caller identity
2. resolve known scope: organization/system/repository/component
3. apply authorization constraints
4. filter by status, type, freshness, and lifecycle
5. use lexical/semantic ranking within the authorized candidate set
6. return memories plus provenance and confidence

This gives semantic retrieval a useful role without asking embeddings to solve identity, hierarchy, or authorization.

## Core components

### 1. Memory API

*Status: read operations implemented as `memory_search` / `memory_get`;
write operations deferred (#3).*

Responsibilities:

- create/propose memory
- approve/reject memory
- retrieve relevant memory
- supersede memory
- expire/archive memory
- record evidence
- audit changes

The API should remain agent-neutral.

### 2. Policy engine

The policy engine determines whether a caller may:

- discover a memory
- read its content
- propose a change
- approve it
- supersede it

The initial implementation can use simple repository/user mappings. More sophisticated implementations may integrate with GitHub teams, enterprise identity, service catalogs, or authorization engines.

### 3. Metadata store

The metadata store is authoritative for:

- memory IDs
- scope
- lifecycle state
- provenance
- relationships
- ACL/policy references
- timestamps
- owners
- review state

*Status:* the v0 decision keeps storage behind the adapter contract; the
OpenViking adapter is the proven path. A separate relational store is not
planned unless a measured need appears.

### 4. Semantic index

The semantic index improves recall across natural-language descriptions.

It should be treated as a **derived index**, not the canonical memory store.

### 5. MCP server

*Status:* `memory_search` and `memory_get` are implemented read-only
([mcp-tools.md](mcp-tools.md)). `memory_propose`, `memory_supersede` and
`memory_feedback` are conceptual and depend on #3.

A coding agent should be able to retrieve memory without knowing which database or embedding model sits behind the service.

## Context assembly

A useful agent context might combine:

```text
Enterprise memory
      +
Domain/system memory
      +
Repository memory
      +
Current task / branch / PR memory
      +
Live repository content
```

The memory service should not indiscriminately send everything. Context assembly needs ranking and a token budget.

## Memory lifecycle

```text
proposed
   │
   ├── rejected
   │
   ▼
approved
   │
   ├── superseded
   ├── expired
   └── archived
```

A future implementation may support automatic approval for low-risk memory classes.

## Provenance

Potential evidence types include:

- git commit
- pull request
- issue
- ADR
- incident
- design document
- service catalog entity
- CI result
- security finding
- human assertion

Provenance enables both trust and revalidation.

## Deployment model

The reference implementation runs locally as a Python package plus a stdio MCP
server, with an optional OpenViking backend (see the Quickstart in the
README). An earlier sketch proposed SQLite/Postgres plus a local embedding
index; that was superseded by [v0-scope.md](v0-scope.md).

The project should avoid requiring a graph database or distributed infrastructure until a use case proves the need.

## Multi-repository and organization context

Cross-repository memory is one of the main reasons for a remote service.

Examples:

- a platform policy that applies to 2,000 repositories
- an API contract owned in one repository and consumed by another
- a migration lesson relevant to an entire application
- a security constraint inherited by every service in a domain

The system therefore needs explicit hierarchy and inheritance rather than treating every repository as an isolated vector namespace.

## Future integrations

Likely integration points include:

- GitHub Apps / webhooks
- developer portals such as Backstage
- Jira or other work-management systems
- CI/CD
- security scanners
- IDE agents
- coding-agent runtimes
- service catalogs
- incident-management systems

The architecture should keep these integrations at the edges rather than coupling the core memory model to any one vendor.
