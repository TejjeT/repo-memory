# OpenViking Mapping

Observed against OpenViking documentation: 2026-10-03

## Research finding

OpenViking already provides:

- resource hierarchy under `viking://resources/...`
- custom memory types
- session-driven memory extraction
- directory-aware + semantic retrieval
- layered context summaries
- accounts/users/groups
- per-resource ACLs with inherited and restricted boundaries

Important implementation detail:

OpenViking's built-in long-term memories are stored under user memory namespaces, while shared material belongs under shared resources.

Therefore a shared engineering assertion is more naturally modeled as a **shared resource/context object** than as ordinary user memory.

## Proposed hierarchy

```text
viking://resources/acme/
  engineering-memory/
    policies/
    domains/
      payments/
        systems/
          settlement-platform/
            assertions/
              EA-002.md
              EA-004.md
              EA-006.md
            repositories/
              payment-api/
              settlement-engine/
              payment-worker/
              legacy-settlement/
```

Repository source itself remains a resource tree rather than being copied into memory.

## Assertion representation

Each assertion could be a Markdown or structured document under the shared resource tree.

Example front matter:

```yaml
id: EA-002
type: incident-derived-constraint
status: approved
importance: critical
owner: payments-platform
scope:
  organization: Acme
  domain: Payments
  system: Settlement Platform
applies_to:
  - repo:payment-api
  - repo:settlement-engine
  - repo:payment-worker
effective_from: 2026-03-02
review_after: 2027-03-02
provenance:
  - incident://INC-412
  - github://acme/settlement-engine/docs/adr/0037.md
```

The body contains the human/agent-readable assertion and rationale.

## ACL mapping

OpenViking ACLs apply to shared resources and support:

- users
- groups
- read/write/manage
- inherited permissions
- restricted inheritance boundaries

This is sufficient for the experiment's Alice/Bob/Carol model at the resource level.

### Limitation to test

repo-memory proposes **source-aligned authorization**.

Example:

EA-002 may be readable to Payments engineers while its incident evidence is restricted.

Questions:

1. Can the assertion safely expose an approved conclusion while provenance remains inaccessible?
2. Should a caller who cannot read a source be allowed to discover that the source exists?
3. If source access is revoked, should assertion access automatically change?
4. Can authorization be recomputed from multiple provenance sources?

These semantics sit above ordinary resource ACL.

## Retrieval mapping

Native OpenViking retrieval can already:

1. constrain search to a target URI
2. apply ACL filtering to returned context records
3. combine semantic retrieval with hierarchy/directory traversal

The repo-memory adapter would add:

1. resolve engineering scope
2. determine applicable assertions
3. filter status/effective dates/supersession
4. enforce source-aligned policy
5. then call OpenViking retrieval/ranking where useful

## Supersession mapping

OpenViking can update, merge, and delete memory/context.

For repo-memory, we should **not** erase superseded engineering rules.

Represent:

```yaml
EA-005:
  status: superseded
  superseded_by: [EA-006]

EA-006:
  status: approved
  supersedes: [EA-005]
```

Retrieval excludes superseded rules by default but history remains inspectable.

This is application semantics layered above OpenViking storage.

## Preliminary result

### OpenViking already solves well

- storage
- hierarchy
- search/indexing
- context retrieval
- multi-agent integration
- authentication
- generic ACLs
- session extraction

### repo-memory may still need to supply

- engineering assertion schema
- applicability inheritance
- typed engineering provenance
- source-aligned authorization policy
- lifecycle/effective-date semantics
- explicit supersession/conflict semantics
- memory-worthiness policy
- engineering-specific evaluation suite

## Current architectural leaning

Do not build a standalone persistence/retrieval engine for the first prototype.

Build:

```text
repo-memory contract + policy/retrieval adapter
                     |
                     v
                 OpenViking
```

Then try to break that design with the payments experiment.

If it survives, the project becomes smaller and more differentiated.
