# Benchmark Framework

This framework gives us a consistent way to compare repository/context/memory systems.

The first version is qualitative. We should add repeatable experiments as the project matures.

## Benchmark dimensions

### 1. Primary unit of memory
What is actually stored: raw conversation, extracted fact, rule/instruction, document/resource, event/episode, knowledge-graph relationship, engineering decision, preference, or arbitrary structured record?

### 2. Scope model
Can memory exist at user, session, repository, directory/component, application/system, domain, organization, enterprise, or arbitrary namespace? Is scope explicit? Is inheritance supported? Can narrower scopes override broader scopes?

### 3. Cross-repository context
Can one memory legitimately apply across repositories? Classify as repository-isolated, manually shared, namespace-based, first-class cross-repo hierarchy, or graph/relationship based.

### 4. Provenance
Does the system retain evidence such as source code citations, commits, PRs, issues, ADRs, conversations, document URIs, or event IDs? Is provenance used only for display or also for revalidation?

### 5. Freshness / invalidation
How does stale context get handled: TTL, validation against source, explicit expiry, manual deletion, source revision tracking, supersession, automatic consolidation, or no documented mechanism?

### 6. Contradictions
What happens when memories conflict: overwrite, latest wins, narrower scope wins, temporal semantics, both returned, human reconciliation, or unspecified?

### 7. Authorization
Distinguish storage authorization, discovery authorization, retrieval authorization, and source alignment. Critical question: is authorization applied before semantic retrieval/ranking?

### 8. Human governance
Can people inspect, edit, approve, reject, delete, and see provenance for memory?

### 9. Memory creation
Is memory captured explicitly, from conversation, from repository activity, by a background observer, by an extraction pipeline, or through API ingestion?

### 10. Retrieval model
Does the system use always-in-prompt context, deterministic lookup, lexical search, vector search, hybrid search, graph traversal, hierarchy/directory traversal, or LLM selection?

### 11. Context assembly
Does it manage token budgets, priority, hierarchy, progressive disclosure, task-aware selection, or proactive versus on-demand retrieval?

### 12. Agent interoperability
Can multiple tools consume the same memory through REST, MCP, CLI, SDK, filesystem, open schema, or only vendor-specific integration?

### 13. Repository portability
Does memory live in the repo, remotely, both, or inside a vendor account? Can it move with the repository or be exported?

### 14. Auditability
Can we answer who created it, when, based on what, who approved it, who used it, when it was last validated, and what replaced it?

### 15. Evaluation
Does the system show that memory improves task success, reduces repeated mistakes, improves compliance, or lowers context cost rather than only improving retrieval similarity?

## Planned profile format

Each researched system should eventually get a machine-readable profile with: system, category, primary_unit, scope, cross_repo, provenance, freshness, contradictions, authorization, governance, creation, retrieval, interoperability, portability, auditability, evaluation, notes, observed_at, and sources.
