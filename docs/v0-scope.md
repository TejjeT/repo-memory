# v0 Scope: Engineering Memory with Retrieval Assist

Decision recorded 2026-10-03. Context: issue #10, PR #13 (live verification
against OpenViking 0.4.23).

## Core v0

- Engineering Assertions (schema, lifecycle, provenance)
- Deterministic scope resolution
- Lifecycle / supersession semantics
- ACL-aware retrieval (authorization constrains the candidate set)
- Provenance capture and redaction
- OpenViking-backed storage path (proven: storage, hierarchy, ACL
  enforcement, indexing — see `docs/openviking-adapter.md`)

## Optional retrieval assist

Embeddings and semantic search may **rank or surface candidates only after
the safe candidate set is determined** by deterministic scope resolution and
authorization. Retrieval assistance is strictly downstream of authority.

## Not v0-critical

- Generic document chunking
- Arbitrary repo-wide semantic search
- Cross-document answer synthesis
- Reranking stacks
- Hybrid retrieval tuning

## Design rule

**RAG may improve relevance; it must not determine authority.**

Scope applicability, authorization, lifecycle filtering, precedence, and
provenance handling remain deterministic and testable (see
`docs/retrieval-contract.md`). No LLM and no vector ranking participates in
those decisions. This is consistent with the repository rule that
authorization must constrain the candidate set before semantic ranking.
