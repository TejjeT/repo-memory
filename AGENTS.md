# AGENTS.md

## Project purpose

repo-memory is a research and reference project for **durable engineering memory**.

The core thesis is that software agents need more than source-code context. They may also need durable engineering assertions such as:

- architectural decisions
- incident-derived constraints
- approved exceptions
- migration lessons
- ownership boundaries
- rejected approaches
- organization-wide policies

The project is intentionally trying to prove where durable engineering memory adds value beyond ordinary repository search and generic RAG.

## Core abstraction

The central object is the **Engineering Assertion**.

An Engineering Assertion includes:

- durable content
- hierarchical engineering scope
- provenance
- lifecycle state
- importance
- optional explicit applicability
- optional overrides
- optional supersession/conflict relationships
- authorization metadata

The machine-readable schema lives at:

- `spec/engineering-assertion.schema.json`

The rationale for required vs optional fields lives at:

- `docs/schema-rationale.md`

## Deterministic semantics are mandatory

Do **not** use an LLM to decide:

- authorization
- scope applicability
- policy precedence
- approved-exception behavior
- supersession
- conflict resolution

These behaviors must remain explicit and testable.

Relevant documentation:

- `docs/applicability-and-precedence.md`
- `docs/retrieval-contract.md`

Current retrieval order is:

```text
identity
  → scope resolution
  → authorization
  → lifecycle filtering
  → applicability / overrides / supersession
  → optional ranking
  → context-budget selection
  → provenance redaction
```

Authorization must constrain the candidate set before semantic ranking.

## Repository architecture

Keep the core package backend-neutral.

```text
src/repo_memory/
  models.py
  loader.py
  policy.py
  serialization.py
  adapters/
    openviking.py
```

The core package should not depend directly on:

- web frameworks
- ORMs
- databases
- vector stores
- LLM SDKs
- MCP SDKs
- OpenViking runtime packages

Vendor-specific logic belongs under `adapters/`.

## OpenViking boundary

OpenViking is currently being tested as infrastructure for:

- shared resource storage
- indexing
- ACLs
- retrieval infrastructure

repo-memory retains responsibility for engineering semantics.

Relevant files:

- `src/repo_memory/adapters/openviking.py`
- `docs/openviking-adapter.md`
- `scripts/openviking_smoke.py`

Do not move engineering precedence or lifecycle semantics into the OpenViking adapter.

## Current experiment

The main research scenario is:

- `research/experiments/payments-system/README.md`

It models:

- organization policy
- system-level constraints
- cross-repository applicability
- repository-specific exceptions
- incident-derived rules
- superseded guidance
- users with different access

The concrete assertions are under:

- `examples/payments/`

Important cases include:

- `EA-001` organization Java runtime policy
- `EA-002` incident-derived idempotency constraint
- `EA-003` approved repository exception
- `EA-005` superseded retry policy
- `EA-006` current retry constraint

## Research discipline

Research is first-class project material.

Relevant folders:

- `research/vendors/`
- `research/open-source/`
- `research/benchmarks/`
- `research/experiments/`

When adding or changing research:

1. Prefer primary sources.
2. Record the observation date.
3. Separate documented behavior from interpretation.
4. Use the benchmark framework where applicable.
5. Do not manufacture differentiation.

See:

- `research/benchmark-framework.md`

## Development workflow

Before completing code changes, run:

```bash
ruff check .
pytest
```

For the optional OpenViking integration:

```bash
pip install -e ".[openviking]"
```

If a live OpenViking server is available:

```bash
OPENVIKING_URL=http://localhost:1933 \
OPENVIKING_API_KEY=... \
python scripts/openviking_smoke.py
```

## Change guidelines

Prefer:

- small changes
- explicit contracts
- focused tests
- readable code
- standard-library abstractions where practical
- adapters over core coupling

Avoid:

- speculative infrastructure
- giant framework additions
- hidden agent state
- implicit policy precedence
- vector search as authorization
- duplicating capabilities already provided by a backend

## Issue discipline

Do not close an issue because implementation is "mostly done."

Close only when its documented exit criteria are satisfied.

Current priority is to prove the OpenViking-backed experiment and then evaluate whether durable engineering memory improves real coding-agent outcomes.

## Guiding question

Before storing something as memory, ask:

> Is this durable engineering context difficult or costly to reconstruct from the current source of truth, and is it likely to materially improve a future engineering decision?

If the answer is no, prefer live retrieval over persistent memory.
