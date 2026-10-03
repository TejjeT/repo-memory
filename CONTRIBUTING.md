# Contributing

repo-memory is an early-stage research and reference project for durable engineering memory.

The project values **clear semantics, small reusable components, and evidence-backed design** over feature count.

## Development setup

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest
ruff check .
```

## Code principles

### Keep the core backend-agnostic

Code under `src/repo_memory/` should not depend directly on:

- web frameworks
- databases or ORMs
- vector stores
- model SDKs
- MCP
- vendor-specific context systems

Adapters belong in separate integration modules.

### Prefer deterministic policy over model judgment

Authorization, applicability, supersession, overrides, and conflict detection should be explicit and testable.

Do not use an LLM where a deterministic rule can define the contract.

### Make relationships explicit

Avoid implicit precedence.

For example:

```json
{
  "type": "approved-exception",
  "overrides": ["EA-001"]
}
```

is preferred over “a narrower exception probably wins.”

### Preserve history

Do not overwrite important historical assertions merely because guidance changed.

Prefer explicit relationships such as:

- `supersedes`
- `superseded_by`
- `conflicts_with`

### Keep examples realistic

Examples should model real engineering situations:

- cross-repository constraints
- incident-derived lessons
- migration rules
- policy exceptions
- ownership boundaries
- rejected approaches

## Tests

Every policy semantic should have a focused unit test.

At minimum, changes to resolution behavior should cover:

- scope inheritance
- organization boundaries
- explicit applicability
- lifecycle
- overrides
- supersession
- conflicts
- authorization hooks

## Research contributions

Research is a first-class contribution.

When adding a vendor, project, or paper:

1. Prefer primary documentation or original papers.
2. Record the observation date.
3. Separate documented behavior from interpretation.
4. Use the common benchmark dimensions.
5. Identify what repo-memory should borrow.
6. Identify what remains unresolved.
7. Do not manufacture differentiation.

See [research/benchmark-framework.md](research/benchmark-framework.md).

## Pull requests

Keep PRs narrow.

A good PR should explain:

- the engineering problem
- the chosen behavior
- why it belongs in the core or an adapter
- tests proving the behavior
- any contract compatibility impact

## Issues

For design discussions, include:

1. scenario
2. missing context
3. why live source retrieval is insufficient
4. proposed durable assertion
5. scope
6. provenance
7. lifecycle implications
8. authorization implications

## Principle

Optimize for **useful durable engineering context**, not maximum stored context.
