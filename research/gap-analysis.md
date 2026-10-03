# Gap Analysis

Initial hypotheses — 2026-10-03

These are hypotheses to investigate, not claims of novelty. Research should actively try to disprove them.

## Gap 1 — Repository memory vs engineering-system memory

Several tools support repository-level memory or instructions. Real enterprise engineering context often spans organization, domain, application/system, repository, and component levels.

Hypothesis: there is room for an explicit engineering hierarchy above repository scope.

Test: model a realistic multi-repository application and compare how existing systems represent inherited and shared memory.

## Gap 2 — Cross-agent portable memory

Most coding products optimize memory for their own agent surfaces. Repository instruction files are portable but static. General memory systems are portable but usually lack engineering semantics.

Hypothesis: a small open memory contract plus MCP/API interface could let multiple coding-agent runtimes, CI agents, and internal agents consume the same governed engineering memory.

Test: build one memory service and demonstrate identical retrieval from at least two agent runtimes.

## Gap 3 — Explicit engineering provenance

GitHub Copilot's code citations and revalidation are a strong benchmark. Engineering decisions may also originate from ADRs, PR discussions, incidents, security findings, service catalogs, tickets, platform policies, and architecture reviews.

Hypothesis: engineering memory benefits from typed provenance rather than only source text references.

Test: create a memory derived from an incident and determine what evidence is needed to trust, invalidate, and audit it later.

## Gap 4 — Supersession and contradiction as first-class behavior

Engineering rules change and multiple statements can be historically true.

Hypothesis: delete-stale-fact is insufficient for some engineering contexts. We may need effective dates, superseded-by, conflicting-with, narrower-scope overrides, and source revisions.

Test: build temporal test cases and compare simple TTL, latest-wins, and explicit supersession.

## Gap 5 — Authorization before semantic retrieval

In enterprise systems, semantic similarity must not decide which protected memories become candidates.

Hypothesis: the safe pipeline is identity, deterministic scope resolution, authorization, lifecycle filtering, then semantic/lexical ranking.

Test: create two users with semantically similar memories but different repository access and prove inaccessible memories never enter the ranking set.

## Gap 6 — Memory selection is more important than memory storage

The harder question may be what should become durable memory at all. Naively storing every inferred fact creates stale facts, duplication, contradictions, review burden, and context pollution.

Hypothesis: repo-memory's most valuable contribution could be a memory-worthiness model for software engineering.

Candidate criteria: not trivially recoverable from current code; likely to matter again; costly to rediscover; actionable; scoping is clear; provenance exists; reasonably stable; costly if missed.

Test: build a labeled set of candidate memories from real PRs and measure human agreement about what deserves persistence.

## Gap 7 — Evaluation tied to engineering outcomes

Memory benchmarks often focus on factual recall. For engineering memory, value may be avoiding rejected approaches, complying with platform constraints, reducing repeated debugging, making correct cross-repo changes, and preserving architectural intent.

Hypothesis: a repository-memory benchmark should measure downstream implementation quality, not just retrieval accuracy.

Test: create tasks where success requires context deliberately absent from the current source tree. Compare repository only, repository plus generic RAG, and repository plus repo-memory.

## Gap 8 — Memory as an organizational feedback loop

A stronger model than memory-as-consumption is engineering work leading to a durable lesson, which becomes a proposed memory, gets reviewed, then improves future engineering work.

Hypothesis: memory can become part of the SDLC itself, similar to tests, documentation, and ADRs.

Test: prototype a GitHub PR workflow where a merged change proposes a memory and future PR review retrieves it.

## Current positioning hypothesis

An open, permission-aware engineering memory layer that preserves durable context across repositories and agent runtimes, with explicit scope, provenance, lifecycle, and governance.

This positioning should change if research shows the problem is already adequately solved. That would be a successful research outcome too.
