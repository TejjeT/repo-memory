# repo-memory

**An open engineering-memory contract for durable context across repositories, systems, and agent runtimes.**

AI coding agents can read code, search history, and retrieve documentation. What they often cannot preserve reliably is the **durable engineering reasoning** that shaped a system:

- architectural decisions
- incident lessons
- approved exceptions
- cross-repository constraints
- ownership boundaries
- rejected approaches
- migration rules
- organization-wide platform policies

> Context tells an agent what exists. Engineering memory explains why it exists, where it applies, and whether it is still valid.

## Project status

Early research + reference implementation.

The project currently focuses on three things:

1. **Engineering Assertion specification** — a typed contract for durable engineering knowledge.
2. **Deterministic policy resolution** — scope, lifecycle, overrides, supersession, and conflicts without asking an LLM to invent precedence.
3. **Industry benchmarking** — comparing GitHub Copilot Memory, OpenViking, Cursor, AgentCore, Graphiti, and related systems to identify real gaps before building infrastructure.

The current architectural hypothesis is:

> repo-memory should be a reusable engineering-memory protocol and policy layer, not another generic vector database.

## Why this exists

A fresh coding agent may be able to reconstruct current code, but important context is often scattered across:

- pull requests and review threads
- ADRs and design documents
- incidents and postmortems
- service catalogs
- security findings
- tickets
- platform policies
- human tribal knowledge

Examples:

- “Java 17 → 25 migrations in this organization also require Jakarta migration.”
- “This repository is temporarily exempt from the Java 25 runtime policy until retirement.”
- “Idempotency keys must survive queue boundaries because a prior incident caused duplicate settlement.”
- “Repository A owns the API contract; repository B owns the implementation.”
- “Gateway retries were deliberately removed; do not reintroduce them.”

These are not just documents. They are **engineering assertions** with scope, evidence, lifecycle, and ownership.

## Core abstraction: Engineering Assertion

A durable assertion is a structured engineering statement.

Example:

```json
{
  "id": "EA-002",
  "type": "incident-derived-constraint",
  "content": "Idempotency keys must survive retries across gateway, queue, and worker boundaries.",
  "scope": {
    "organization": "Acme",
    "domain": "Payments",
    "system": "Settlement Platform"
  },
  "applies_to": [
    {"kind": "repository", "id": "payment-api"},
    {"kind": "repository", "id": "settlement-engine"},
    {"kind": "repository", "id": "payment-worker"}
  ],
  "status": "approved",
  "importance": "critical",
  "provenance": [
    {"type": "incident", "uri": "incident://INC-412"},
    {"type": "adr", "uri": "github://acme/settlement-engine/docs/adr/0037.md"}
  ],
  "created_at": "2026-03-02T00:00:00Z"
}
```

The draft machine-readable contract lives at:

- [spec/engineering-assertion.schema.json](spec/engineering-assertion.schema.json)

## Deterministic policy semantics

The policy engine does **not** use an LLM to decide which rules win.

Resolution order:

```text
authorization
    ↓
lifecycle
    ↓
scope / explicit applicability
    ↓
supersession
    ↓
explicit overrides
    ↓
conflict reporting
    ↓
stable ordering
```

See:

- [docs/applicability-and-precedence.md](docs/applicability-and-precedence.md)

Important rules include:

- authorization constrains the candidate set first
- parent scopes apply to descendants
- explicit repository targets cannot cross the organization boundary in v0
- exceptions override only assertion IDs they explicitly name
- superseded assertions remain historically inspectable
- conflicts are surfaced, not guessed away

## Repository layout

```text
repo-memory/
├── spec/
│   └── engineering-assertion.schema.json
├── src/repo_memory/
│   ├── models.py
│   ├── loader.py
│   └── policy.py
├── tests/
├── examples/
│   └── payments/
├── docs/
├── research/
│   ├── benchmarks/
│   ├── vendors/
│   ├── open-source/
│   └── experiments/
└── ROADMAP.md
```

### Design boundary

The core package intentionally does **not** depend on:

- a web framework
- an ORM
- a vector database
- an LLM SDK
- OpenViking
- MCP

Those integrations belong at the edges.

That keeps the contract and policy semantics reusable across storage and agent runtimes.

## Agent instructions

The canonical repository instructions live in:

- [AGENTS.md](AGENTS.md)

Agent-specific bootstrap files should reference the canonical instructions rather than duplicate them.

For Claude Code:

- [CLAUDE.md](CLAUDE.md)

## Quickstart

Requires Python 3.11+.

```bash
git clone https://github.com/TejjeT/repo-memory.git
cd repo-memory

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
pytest
ruff check .
```

## Example usage

```python
from datetime import UTC, datetime

from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext, resolve_assertions

assertion = EngineeringAssertion(
    id="EA-001",
    type="policy",
    content="New Java services must target Java 25.",
    scope=Scope(organization="Acme"),
    status="approved",
    importance="high",
    provenance=(Provenance(type="policy", uri="policy://PLAT-JAVA-2026-04"),),
    created_at=datetime(2026, 4, 1, tzinfo=UTC),
)

result = resolve_assertions(
    [assertion],
    ResolutionContext(
        scope=Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement Platform",
            repository="payment-api",
        ),
        when=datetime.now(UTC),
    ),
)

print([item.id for item in result.active])
```

## Research program

The research folder is first-class project material, not background notes.

Current work includes:

- industry landscape
- common benchmark framework
- GitHub Copilot Memory deep dive
- OpenViking deep dive
- Copilot vs OpenViking vs repo-memory benchmark
- a multi-repository payments experiment
- coding-agent evaluation
- memory-worthiness research

Start here:

- [research/README.md](research/README.md)
- [research/industry-landscape.md](research/industry-landscape.md)
- [research/benchmarks/copilot-openviking-repomemory.md](research/benchmarks/copilot-openviking-repomemory.md)
- [research/experiments/payments-system/README.md](research/experiments/payments-system/README.md)
- [research/experiments/coding-agent/README.md](research/experiments/coding-agent/README.md)

## Current architectural hypothesis

The first implementation should avoid rebuilding generic memory infrastructure.

A likely architecture is:

```text
GitHub / ADRs / Incidents / Policies / Catalog
                    ↓
           Engineering Assertions
                    ↓
     repo-memory contract + policy layer
                    ↓
          pluggable context backend
              (e.g. OpenViking)
                    ↓
            coding-agent runtimes
```

The backend remains intentionally replaceable.

## Design principles

### Engineering semantics before embeddings

Identity, scope, authorization, lifecycle, and applicability are deterministic metadata problems.

Semantic ranking may improve recall later, but it must not reconstruct access boundaries or policy precedence.

### Evidence matters

Important assertions should point back to the commit, ADR, PR, incident, policy, catalog entity, or human decision that supports them.

### Memory should be selective

The project is not trying to persist every fact an LLM notices.

A useful durable assertion should be difficult or costly to rediscover, likely to matter again, actionable, scoped, and evidence-backed.

### Forgetting and supersession are features

Engineering knowledge changes. A memory system that only accumulates facts eventually becomes a misinformation system.

## What repo-memory is not

It is not intended to be:

- another generic RAG framework
- a repository code index
- a hidden agent scratchpad
- a vector database wrapper
- an ungoverned knowledge graph
- a replacement for source-of-truth systems
- a dump of every conversation

## Roadmap

Near-term focus:

- finish v0 contract semantics
- validate example assertions
- build the OpenViking-backed experiment
- test permission-aware retrieval
- evaluate cross-repository tasks
- compare repo-only vs live retrieval vs durable engineering assertions

See [ROADMAP.md](ROADMAP.md).

## Contributing

Architecture critiques and counterexamples are especially useful.

If an existing system already solves a problem better, the project should adopt it rather than recreate it.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
