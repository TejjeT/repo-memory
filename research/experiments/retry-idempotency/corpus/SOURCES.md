# Corpus sources

Ordinary reference documents for the retry/idempotency experiment. Both
retrieval arms (generic retrieval and repo-memory) may access these; the
repository-only arm may not.

## Fact equivalence

| Document | Mirrors | Shared underlying facts |
|---|---|---|
| `retry-policy.md` | EA-006 (current retry policy) | Retry at exactly one orchestration layer; gateway/client retries must not both be enabled; transient → retry, permanent → stop |
| `idempotency-guide.md` | EA-002 (idempotency constraint) | One idempotency key per batch, generated once, reused across all retry boundaries; regenerated or missing keys cause duplicate settlement |

The repo-memory arm additionally receives the EA-002/EA-006 assertions
themselves (with permitted provenance). The experiment measures whether
the structured assertions change implementation correctness beyond what
the ordinary documents already provide.

## Withheld in all arms

Restricted incident background is withheld from every condition,
including both retrieval arms:

- INC-412 details (the duplicate-settlement incident behind EA-002)
- INC-463 details (behind EA-006)
- ADR-37 / ADR-41 full text (only their conclusions appear above)

## Repository-only knowledge

The repository-only arm receives exactly: `fixture/worker.py`,
`fixture/gateway.py`, and the task text ("Add retry handling for
transient settlement submission failures in `settle_batch`."). No
corpus documents, no assertions, no experiment history, no
evaluator-only expected answers.
