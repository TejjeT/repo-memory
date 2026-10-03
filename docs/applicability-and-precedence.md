# Applicability and Precedence

This document defines deterministic v0 semantics for resolving active Engineering Assertions.

The policy engine must not ask an LLM to invent precedence.

## Resolution pipeline

Given a target scope and time:

1. **Authorize**
   - Assertions that the caller is not allowed to discover/read do not enter the candidate set.

2. **Lifecycle filter**
   - status must be `approved`
   - `effective_from` must be in the past/present
   - `expires_at` must be in the future, if present

3. **Applicability**
   - a parent scope applies to its descendants
   - an explicit `applies_to` repository target may make an assertion applicable to that repo

4. **Supersession**
   - if an active assertion supersedes another candidate assertion, the older assertion is excluded from normal retrieval
   - superseded assertions remain inspectable historically

5. **Approved exception precedence**
   - a narrower `approved-exception` may shadow a broader `policy`
   - it does not automatically suppress unrelated constraints

6. **Conflicts**
   - declared conflicts between remaining assertions are surfaced
   - v0 does not silently pick a winner

7. **Ordering**
   - narrower scope first
   - higher importance next
   - stable ID ordering last

## Why authorization comes first

Authorization must constrain the candidate set before semantic ranking or context assembly.

A caller should not be able to infer the existence of inaccessible engineering memory merely because it was semantically similar.

## Scope inheritance

The hierarchy is:

```text
organization
  → domain
    → system
      → repository
        → component
          → branch
            → pull request
```

A populated level must match the target at the same level.

Example:

```yaml
scope:
  organization: Acme
  domain: Payments
```

applies to descendants inside `Acme / Payments`.

It does not apply to `Acme / Identity`.

## Explicit applicability

An assertion may name repositories outside the most-specific scope fields through `applies_to`.

This is intended for rules discovered in one system but explicitly applicable to several repositories.

Explicit applicability must be auditable and should not become a substitute for sloppy scoping.

## Exceptions

Example:

Enterprise policy:

> New Java services target Java 25.

Repository exception:

> legacy-settlement remains on Java 17 until retirement milestone M-2027-01.

For `legacy-settlement`, the approved exception shadows the broader runtime policy.

The broader policy remains active everywhere else.

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

Normal retrieval returns EA-006.

Historical/audit retrieval may return both.

## Conflicts

Two assertions may both remain active but be explicitly incompatible.

Example:

```text
EA-100 conflicts_with EA-101
```

v0 behavior:

- return both
- emit a conflict marker
- require policy/human reconciliation

The engine does not use an LLM to guess which organizational rule is authoritative.

## Future work

Potential future semantics:

- exception-specific `overrides` relationships
- applicability expressions beyond repository IDs
- policy categories to prevent exceptions shadowing unrelated policies
- source-confidence weighting
- effective-date intervals
- conflict resolution workflows
