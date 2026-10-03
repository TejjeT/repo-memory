# Architecture

## Goal

repo-memory provides durable engineering memory that can be retrieved by humans and AI agents without forcing every tool to implement its own memory subsystem.

The architecture deliberately separates **sources of truth** from **durable learned context**.

## High-level architecture

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

A relational store is the simplest starting point.

### 4. Semantic index

The semantic index improves recall across natural-language descriptions.

It should be treated as a **derived index**, not the canonical memory store.

### 5. MCP server

An MCP interface can expose a small set of tools such as:

- `memory.search`
- `memory.get`
- `memory.propose`
- `memory.supersede`
- `memory.feedback`

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

The earliest reference implementation should be easy to run locally:

```text
API/MCP server
    │
    ├── SQLite/Postgres
    └── local embedding/index option
```

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
