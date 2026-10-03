# repo-memory

**Persistent, permission-aware memory for software repositories and AI coding agents.**

AI coding agents can read a repository. They can inspect its current state, search its history, and retrieve documentation. What they usually cannot do is remember the *reasoning* that shaped the repository — architectural decisions, failed approaches, migration lessons, ownership boundaries, security constraints, and organization-wide engineering context.

**repo-memory** explores a durable memory layer for repositories and the organizations around them.

> Context tells an agent what exists. Memory helps explain why it exists.

## The problem

A fresh coding agent entering a repository may be able to reconstruct a lot from source code, but important context is often distributed across:

- pull requests and review threads
- ADRs and design docs
- incidents and postmortems
- Slack or Teams discussions
- issue trackers
- developer portals and service catalogs
- security findings
- tribal knowledge

Examples of context that should survive individual conversations:

- "Java 17 → 25 migrations in this organization also require Jakarta migration."
- "This authentication pattern was rejected because it bypassed the enterprise identity layer."
- "Repository X owns the API contract; repository Y owns the runtime."
- "A previous implementation caused a production incident; do not reintroduce it."
- "This odd-looking design is intentional and documented in ADR-27."

Without durable memory, each agent starts from zero and repeatedly rediscovers the same facts.

## Thesis

Repository memory should be:

1. **Hierarchical** — organization → domain → system → repository → component → branch/PR.
2. **Permission-aware** — retrieval must respect the caller's access.
3. **Provenanced** — memories should link back to evidence.
4. **Freshness-aware** — memory can decay, expire, or require reconfirmation.
5. **Human-governed** — important memories can be proposed by agents but approved by people.
6. **Agent-neutral** — Claude Code, Codex, Copilot, IDE agents, CI agents, and internal tooling should be able to consume the same memory.
7. **Useful without replacing source-of-truth systems** — memory complements Git, documentation, service catalogs, and ticketing systems.

## A simple mental model

```text
Organization
   │
   ├── Domain
   │     │
   │     └── System / Application
   │             │
   │             └── Repository
   │                    │
   │                    ├── Component
   │                    └── Branch / PR
   │
   └── Enterprise policies and learned patterns
```

Each memory has content plus metadata such as scope, provenance, permissions, confidence, freshness, and relationships.

## Initial workflow

The first end-to-end workflow we want to prove:

```text
Agent investigates issue
        ↓
Discovers durable context
        ↓
Proposes a memory
        ↓
Human reviews / approves
        ↓
Memory becomes available to future agents
        ↓
Relevant memory is injected on demand
```

This makes memory a continuously improving organizational asset rather than a static vector index.

## What repo-memory is not

This project is **not** intended to be:

- another generic RAG framework
- a replacement for Git history
- a documentation dumping ground
- a hidden agent scratchpad
- an ungoverned knowledge graph
- a system that blindly stores every conversation

The goal is to identify the small amount of durable context that materially improves future engineering decisions.

## Architecture direction

The initial architecture separates four concerns:

- **Ingestion** — proposed memories from humans, agents, GitHub, CI/CD, service catalogs, incidents, etc.
- **Memory service** — validation, lifecycle, provenance, scope, and policy.
- **Storage / retrieval** — deterministic metadata filtering plus semantic retrieval where appropriate.
- **Interfaces** — REST API, MCP server, CLI, and integrations.

See [docs/architecture.md](docs/architecture.md).

## Memory model

A memory is more than text.

```json
{
  "id": "mem_123",
  "scope": {
    "organization": "example",
    "system": "payments",
    "repository": "checkout-service"
  },
  "type": "architecture-decision",
  "content": "Use the shared auth middleware for all externally exposed endpoints.",
  "provenance": [
    {
      "type": "adr",
      "uri": "github://example/checkout-service/docs/adr/0027.md"
    }
  ],
  "confidence": 0.98,
  "status": "approved",
  "freshness": {
    "review_after": "2027-01-01"
  }
}
```

See [docs/memory-model.md](docs/memory-model.md).

## Design principles

### Deterministic before semantic

If a caller asks for memories about a known repository, system, policy, or component, metadata and relationships should narrow the search first. Embeddings are useful for relevance, not for reconstructing identity and access boundaries.

### Memory should carry evidence

An important memory without provenance is just another assertion. Wherever possible, a memory should reference the commit, ADR, issue, incident, PR, or human decision that created it.

### Retrieval is part of authorization

It is not sufficient to authorize the API call and then search a global vector store. Permissions must constrain the candidate memory set *before* semantic ranking.

### Agents propose; humans govern

Agents are excellent at identifying reusable context. They should be able to propose memory. High-impact memory should have explicit ownership and review.

### Forgetting is a feature

Engineering knowledge changes. Memories need expiry, supersession, confidence, and review semantics.

## Roadmap

The first milestones are intentionally small:

- **M0 — Contract:** memory schema + API semantics
- **M1 — Local prototype:** save, search, recall, supersede
- **M2 — MCP interface:** expose repo memory to coding agents
- **M3 — GitHub integration:** propose memories from PRs/issues
- **M4 — Permission model:** organization/repository/user-aware retrieval
- **M5 — Evaluation:** measure whether memory actually improves agent outcomes

See [ROADMAP.md](ROADMAP.md).

## Open questions

Some of the questions this project will explore:

- What deserves to become durable memory?
- What should remain in source systems and simply be retrieved?
- How should enterprise, system, and repository memory interact?
- How do we detect contradictory or stale memories?
- When should memory be automatically accepted versus reviewed?
- Can we measure memory quality using downstream engineering outcomes?
- How much context should an agent receive proactively versus fetch on demand?
- How should memory work across repositories while preserving access controls?

## Status

**Early design / experimental.**

The goal right now is to make the model precise, build a deliberately small reference implementation, and validate it against real software-engineering workflows.

## Contributing

Ideas, counterexamples, architecture critiques, and experiments are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
