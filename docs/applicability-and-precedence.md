# Applicability and Precedence

This document defines deterministic v0 semantics for resolving active Engineering Assertions.

The policy engine must not ask an LLM to invent precedence.

## Resolution pipeline

Given a target scope and time:

1. **Authorize**
   - inaccessible assertions never enter the candidate set

2. **Lifecycle filter**
   - status must be `approved`
   - `effective_from` must be active
   - `expires_at` must not have passed

3. **Applicability**
   - parent scopes apply to descendants
   - explicit repository targets may extend applicability across systems
   - explicit targeting may not cross the organization boundary in v0

4. **Supersession**
   - an active successor removes a superseded assertion from normal retrieval
   - history remains inspectable

5. **Explicit overrides**
   - an `approved-exception` overrides only assertion IDs named in its `overrides` list
   - narrower scope alone is never sufficient to suppress unrelated policy

6. **Conflicts**
   - declared conflicts are surfaced
   - v0 does not silently choose a winner

7. **Ordering**
   - narrower scope first
   - higher importance next
   - stable ID ordering last

## Why authorization comes first

Authorization must constrain the candidate set before semantic ranking or context assembly.

A caller should not be able to infer inaccessible engineering memory merely because it is semantically relevant.

## Scope hierarchy

```text
organization
  → domain
    → system
      → repository
        → component
          → branch
            → pull request
```

A populated level must match the target at the same level for normal inheritance.

## Explicit applicability

`applies_to` exists for legitimate cross-system cases.

Example: an incident-derived rule from Settlement Platform may explicitly apply to `payment-worker` even when that repository is cataloged under another system.

v0 guardrail:

> explicit repository targeting must stay inside the same organization.

This avoids turning a convenient repository ID match into a cross-tenant data leak.

## Exceptions

Example enterprise policy:

> New Java services target Java 25.

Repository exception:

> legacy-settlement remains on Java 17 until retirement milestone M-2027-01.

The exception must say:

```yaml
overrides:
  - EA-001
```

It does **not** suppress unrelated enterprise policies.

## Supersession

Historical rules are not deleted.

```text
EA-005
  status: superseded
  superseded_by: [EA-006]

EA-006
  status: approved
  supersedes: [EA-005]
```

Normal retrieval returns EA-006. Audit retrieval may return both.

## Conflicts

```text
EA-100 conflicts_with EA-101
```

v0 behavior:

- return both active assertions
- emit a conflict marker
- require policy or human reconciliation

The engine does not ask an LLM to decide which organizational rule is authoritative.

## Future work

Potential future semantics:

- richer target expressions
- explicit tenant federation
- policy categories
- source-confidence weighting
- effective-date intervals
- conflict resolution workflows
