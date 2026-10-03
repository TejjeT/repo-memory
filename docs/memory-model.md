# Memory Model

## Objective

A memory should be a durable, inspectable engineering assertion — not an opaque vector.

## Proposed schema

```json
{
  "id": "mem_01J...",
  "type": "architecture-decision",
  "content": "External endpoints must use the shared authentication middleware.",
  "scope": {
    "organization": "example",
    "domain": "commerce",
    "system": "checkout",
    "repository": "checkout-service",
    "component": null
  },
  "status": "approved",
  "importance": "high",
  "confidence": 0.98,
  "provenance": [
    {
      "type": "adr",
      "uri": "github://example/checkout-service/docs/adr/0027.md",
      "revision": "abc123"
    }
  ],
  "relationships": [
    {
      "type": "applies-to",
      "target": "repo://example/checkout-service"
    }
  ],
  "permissions": {
    "inherit_from_scope": true
  },
  "freshness": {
    "created_at": "2026-10-03T00:00:00Z",
    "review_after": "2027-01-03T00:00:00Z"
  },
  "created_by": {
    "type": "agent",
    "id": "coding-agent"
  },
  "approved_by": {
    "type": "user",
    "id": "alice"
  }
}
```

## Memory types

The initial taxonomy should remain intentionally small.

### architecture-decision

A durable architectural rule or decision.

Example:

> All externally exposed services use the shared identity middleware.

### constraint

A requirement that limits valid implementation choices.

Example:

> This application cannot use public internet egress.

### migration-lesson

A reusable lesson discovered during a migration.

Example:

> Java 17 → 25 migrations also require Jakarta namespace changes in repositories using the legacy servlet stack.

### incident-lesson

Context derived from an incident or postmortem.

Example:

> Do not enable retry at both the gateway and client layers for this downstream API.

### ownership

Non-obvious responsibility or boundary.

Example:

> The platform team owns the API contract; the payments team owns the service implementation.

### convention

A project or organization convention that is not obvious from tooling.

### rejected-approach

An approach that was deliberately evaluated and rejected.

This is especially valuable to agents because code alone usually cannot explain why an apparently reasonable implementation should not be attempted again.

## Scope

Scope answers: **where does this memory apply?**

A memory may live at one or more levels:

```text
organization
domain
system
repository
component
branch / pull request
```

A retrieval request may inherit relevant memories from parent scopes.

For example:

```text
org policy
  ↓
payments-domain constraint
  ↓
checkout-system decision
  ↓
checkout-service repo memory
```

## Provenance

A memory should ideally have evidence.

Provenance enables:

- verification
- revalidation
- trust scoring
- automated invalidation
- navigation back to the source

The source of truth remains the referenced artifact. repo-memory stores the durable assertion and its relationship to that artifact.

## Confidence vs importance

These are different.

**Confidence** asks:

> How certain are we that this assertion is correct?

**Importance** asks:

> How costly would it be for an agent to miss this assertion?

A security rule can be high importance even if it is awaiting confirmation.

## Supersession

Engineering context changes. Updating memory in place destroys history.

Instead:

```text
mem_A: "Use library v1"
       │
       └── superseded-by → mem_B

mem_B: "Use library v2"
```

Historical memory remains inspectable but should not normally be returned as active guidance.

## Contradictions

The system should eventually detect memories that appear inconsistent within overlapping scopes.

Possible handling:

1. return both with an explicit conflict marker
2. prefer narrower scope when policy allows
3. prefer newer approved memory
4. require human reconciliation for high-impact conflicts

The system should not silently ask an LLM to choose which organizational rule is authoritative.

## Freshness

Possible freshness semantics:

- `review_after`
- `expires_at`
- last source verification time
- source revision
- source still exists
- dependent artifact changed

Freshness should affect retrieval but should not necessarily delete historical knowledge.

## Memory quality

A good durable memory is:

- specific
- actionable
- scoped
- evidence-backed
- unlikely to be obvious from the current source tree
- valuable to a future engineer or agent

A bad durable memory is:

> This repo uses Python.

That can simply be observed.

A better memory is:

> Although this repository contains both Python 3.11 and 3.12 configurations, production must remain on 3.11 until the native dependency in issue #142 is replaced.

## Open design question

The most important product question may be:

> **What deserves to become memory?**

The project should treat memory selection as a first-class problem rather than assuming more stored context is always better.
