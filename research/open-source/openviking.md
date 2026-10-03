# OpenViking

Observed: 2026-10-03

## Why this matters

OpenViking is a much closer architectural neighbor to repo-memory than a conventional memory library.

It describes itself as a context database for AI agents and unifies:

- resources
- memories
- skills

inside a virtual filesystem.

It should be treated as a possible **foundation/integration target**, not merely a competitor.

## Core model

### Resources

Reference material such as:

- documents
- repositories
- other knowledge sources

### Memories

Long-term context extracted from sessions or explicitly recorded.

Current documented memory types include categories such as:

- profile
- preferences
- entities
- events
- identity
- cases
- trajectories
- experiences

Custom memory types are also supported.

### Skills

Reusable task instructions and supporting resources.

## Hierarchical context

Context is addressed by viking URIs.

The filesystem model is important because it gives agents deterministic navigational structure in addition to semantic retrieval.

OpenViking generates layered context:

- L0: short abstract
- L1: overview
- L2: original detail

This supports progressive disclosure.

## Retrieval

OpenViking combines semantic matching with directory traversal.

The architecture therefore already demonstrates an important principle we had proposed:

> Narrow context structurally before loading/ranking full detail.

This idea is not unique to repo-memory.

## Memory extraction

Applications can append messages to sessions and commit those sessions for asynchronous extraction.

Existing memories inform subsequent extraction.

Depending on memory policy and schemas, extraction may:

- create
- update
- merge
- skip
- delete

memory content.

OpenViking also supports explicit memory consolidation for deduplication/normalization.

## Agent integrations

OpenViking documents integrations with several agent runtimes and clients including:

- Claude Code
- Codex
- Cursor
- MCP clients
- LangChain/LangGraph
- other coding agents

This gives it substantially stronger interoperability than vendor-native memory systems.

## Authentication and authorization

Current OpenViking server documentation includes:

Authentication modes:
- API key
- OIDC
- LDAP
- trusted gateway
- dev/local

Identity model:
- account
- user
- roles
- groups

Roles:
- ROOT
- ADMIN
- USER

Resource authorization:
- ACLs on files/directories
- read/write/manage permissions

This is mature enough that repo-memory should not treat generic RBAC/ACL as differentiation.

## Key distinction from repo-memory hypothesis

OpenViking has a general context model.

A repository is naturally represented as a resource.

Its memories are primarily oriented around user/peer/session-derived context and flexible custom types.

repo-memory's proposed abstraction is narrower:

> a durable engineering assertion with explicit engineering applicability, evidence, ownership, and lifecycle.

Example:

"All payment API consumers must preserve idempotency keys across retries because incident INC-412 demonstrated duplicate-settlement risk."

For repo-memory, this object might explicitly encode:

- organization
- domain
- system
- affected repositories/components
- provenance type = incident
- source = INC-412
- owning team
- importance
- effective date
- review date
- superseded-by
- authorization references

OpenViking can likely store this information, especially through custom types/resources.

The open question is whether making those semantics first-class creates enough value to justify a separate protocol/service.

## Benchmark profile

Primary unit:
- resource
- memory
- skill

Scope:
- account/user/peer/path-based hierarchy

Cross-repo:
- supported structurally through shared resources and hierarchy

Provenance:
- session/resource context can be preserved
- not inherently an engineering typed-provenance model

Freshness:
- long-term dynamic memory
- update/merge/delete/consolidate
- resource refresh/update

Contradictions:
- extraction/consolidation can reconcile state
- no engineering-specific explicit conflict relationship identified in current review

Authorization:
- strong server-level auth + resource ACL model

Human governance:
- browse/read/write/delete via filesystem/API tooling
- visibility is a design goal

Creation:
- session extraction
- explicit remember/write
- resource ingestion

Retrieval:
- semantic + directory-aware
- layered summaries

Interoperability:
- broad

Portability:
- open source/self-hostable

Auditability:
- retrieval trajectories are observable
- filesystem state is inspectable
- additional engineering approval lineage would need to be modeled

Evaluation:
- OpenViking publishes context/memory evaluation work; deeper methodology review remains on backlog

## Ideas worth borrowing

1. **Resource / memory / skill separation**
2. **Filesystem-like context organization**
3. **Progressive L0/L1/L2 loading**
4. **Observable retrieval paths**
5. **Cross-agent integration**
6. **Session-to-memory extraction**
7. **Consolidation/deduplication**
8. **Pluggable authentication**
9. **Per-resource ACLs**

## Potential integration strategy

Rather than rebuilding general memory/storage infrastructure:

    repo-memory engineering contract
              |
              v
        OpenViking adapter
              |
      resources / memories
              |
      multi-agent consumers

A future prototype should test this directly.

If OpenViking can cleanly support all required engineering semantics through custom types, hierarchy, ACLs, and provenance, repo-memory may be more valuable as a **specification + policy layer + evaluation suite** than as a standalone database.

## Research questions still open

- Can ACLs inherit cleanly through application/system/repository hierarchies?
- How would source-system access revocation propagate?
- How are custom memory schemas versioned?
- Can provenance reference multiple external sources robustly?
- How does memory consolidation behave with intentionally conflicting historical facts?
- Can effective-date and supersession semantics be modeled without custom application logic?
- How well does OpenViking retrieval work on multi-repository engineering tasks?
- What do its published benchmarks actually measure?

## Sources

- https://openviking.ai/docs
- https://docs.openviking.ai/en/concepts/02-context-types
- https://docs.openviking.ai/en/concepts/08-session
- https://docs.openviking.ai/en/guides/04-authentication
- https://docs.openviking.ai/en/context-compilation/06-memory-consolidation
- https://github.com/volcengine/OpenViking
