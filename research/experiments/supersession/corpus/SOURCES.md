# Corpus sources

Ordinary reference documents for the supersession experiment. Both
retrieval arms (generic retrieval and repo-memory) may access these; the
repository-only arm may not.

## Fact equivalence

| Document | Mirrors | Shared underlying facts |
|---|---|---|
| `retry-policy-current.md` | EA-006 (current) | Retry at exactly one orchestration layer; worker owns it; gateway `max_retries` must be 0; the old 3-attempt gateway guidance is superseded |
| `retry-policy-history.md` | EA-005 (historical) | Gateway retries up to 3 were allowed 2025-08-01 to 2026-06-12; clearly marked superseded |

The repo-memory arm additionally receives the EA-005/EA-006 assertions
themselves via the authenticated MCP read path (with permitted
provenance; restricted incident identifiers withheld). The experiment
measures whether the structured assertions change implementation
correctness beyond what the ordinary documents already provide, and
whether stale guidance is rejected.

## Withheld in all arms

Restricted incident background is withheld from every condition,
including both retrieval arms and the MCP-delivered context:

- INC-463 details (the incident behind EA-006)

Only the conclusions appear in the permitted sources above.

## Repository-only knowledge

The repository-only arm receives exactly: `fixture/worker.py`,
`fixture/gateway.py`, and the task text ("Bring the settlement retry
configuration into compliance with current policy."). No corpus
documents, no assertions, no experiment history, no evaluator-only
expected answers.
