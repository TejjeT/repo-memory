# Retrieval Contract

This document defines the v0 retrieval contract for Engineering Assertions.

The goal is to make retrieval **predictable, permission-aware, and backend-independent**.

## Inputs

A retrieval request contains:

- caller identity
- target engineering scope
- current time
- optional query text
- optional assertion-type filter
- optional maximum result count
- optional context/token budget

Conceptually:

```text
retrieve(
  caller,
  scope,
  when,
  query?,
  types?,
  limit?,
  budget?
)
```

## Required pipeline

The order is normative.

```text
1. identity resolution
        ↓
2. scope resolution
        ↓
3. authorization
        ↓
4. lifecycle filtering
        ↓
5. applicability / override / supersession
        ↓
6. optional lexical / semantic ranking
        ↓
7. context-budget selection
        ↓
8. provenance redaction
        ↓
9. response
```

Semantic ranking must never run across assertions the caller is not authorized to discover.

## 1. Identity resolution

The adapter resolves the caller into the authorization model used by the deployment.

Examples:

- GitHub user/team membership
- OIDC subject
- service account
- enterprise identity group

The core contract does not define an identity provider.

In the v0.2 assembler (`src/repo_memory/context.py`), the resolved caller
is represented as a `Caller` (identity plus granted source URI prefixes).
`ContextAssembler.for_caller` binds the assertion, evidence, and provenance
authorization hooks to that one identity, so all three decisions trace to
the same authenticated caller. Omitted hooks default to the caller's grants
(deny by default) instead of permissive behavior. The plain constructor
keeps permissive-when-omitted defaults for backward compatibility; it is
not a production identity boundary.

## 2. Scope resolution

The caller supplies or the adapter derives a target hierarchy:

```text
organization
  → domain
    → system
      → repository
        → component
          → branch
            → pull request
```

Known identifiers should be resolved deterministically from catalogs or repository metadata where possible.

An LLM should not guess ownership or scope relationships.

## 3. Authorization

Authorization is evaluated before an assertion enters the candidate set.

An authorization implementation may consider:

- assertion scope
- caller groups/roles
- repository permissions
- source-system permissions
- assertion-specific policy references
- provenance access controls

### Discovery vs content

Deployments may distinguish:

- **discover** — caller may know an assertion exists
- **read** — caller may read its content
- **read_provenance** — caller may inspect source evidence

v0 permits an approved engineering conclusion to be readable while some underlying evidence is redacted, when policy explicitly allows that.

## 4. Lifecycle filtering

Normal retrieval includes only assertions that:

- have status `approved`
- are effective at the requested time
- have not expired

Historical/audit retrieval is a separate mode and may include:

- superseded
- expired
- archived
- rejected

## 5. Applicability and precedence

Use the deterministic rules in:

- [applicability-and-precedence.md](applicability-and-precedence.md)

Normal retrieval applies:

- hierarchy inheritance
- explicit repository applicability
- organization-boundary guardrails
- supersession
- explicit overrides
- conflict detection

## 6. Ranking

Ranking is optional.

A backend may use:

- exact metadata match
- lexical search
- embeddings
- hybrid retrieval
- graph relationships

Ranking occurs **only after** authorization and applicability.

### Required deterministic signals

Before semantic relevance, implementations should preserve:

1. scope specificity
2. importance
3. lifecycle validity
4. explicit applicability

Semantic relevance must not make a broad low-importance assertion outrank a critical directly applicable assertion without an explicit ranking policy.

## 7. Context-budget selection

Returning every applicable assertion is not always useful.

v0 selection should support:

- maximum result count
- optional token/context budget
- deterministic priority ordering

Default priority:

1. critical direct/narrow-scope assertions
2. high-importance direct/narrow-scope assertions
3. broader inherited assertions
4. lower-importance assertions

Conflicted assertions are returned together when either member is selected so the conflict is not hidden.

## 8. Provenance redaction

An assertion may reference evidence the caller cannot access.

Response behavior should distinguish:

### Full provenance

Caller may access the source:

```json
{
  "type": "incident",
  "uri": "incident://INC-412"
}
```

### Redacted provenance

Caller may use the approved assertion but may not inspect the source:

```json
{
  "type": "incident",
  "redacted": true
}
```

### Hidden assertion

If policy does not allow discovery of the assertion itself, it must not appear in retrieval output or ranking metadata.

## Response shape

A backend-neutral response should include:

```json
{
  "assertions": [
    {
      "id": "EA-002",
      "content": "...",
      "type": "incident-derived-constraint",
      "importance": "critical",
      "scope": {},
      "provenance": [],
      "status": "approved"
    }
  ],
  "conflicts": [],
  "truncated": false
}
```

Future versions may add ranking explanations and retrieval traces.

## Worked examples

### Example A — repository-only caller

Bob can access `payment-api` but not `settlement-engine`.

A request targeting `payment-api` may return an approved cross-repo API constraint if policy grants Bob discovery/read access.

It must not expose restricted `settlement-engine` internals or incident evidence merely because those sources contributed to the assertion.

### Example B — exception precedence

Target:

`Acme / Payments / Settlement Platform / legacy-settlement`

Candidates:

- EA-001 — organization Java 25 policy
- EA-003 — approved repository exception overriding EA-001

Normal result:

- EA-003

EA-001 remains available to historical/audit retrieval.

### Example C — supersession

Candidates:

- EA-005 — old retry guidance
- EA-006 — active replacement that supersedes EA-005

Normal result:

- EA-006

### Example D — semantic search

Query:

> retry handling for settlement submission

The backend may semantically rank EA-006 highly.

It may only rank assertions that survived authorization, lifecycle, and applicability filtering.

## Non-goals

The v0 contract does not define:

- a specific embedding model
- a vector database
- identity-provider integration
- a universal RBAC language
- automatic source-access synchronization
- a fixed tokenizer

Those belong to adapters and deployment policy.

## Provider trust boundary

Evidence providers receive the resolved safe candidates with their
unredacted provenance, because a provider needs source details to scope
retrieval. Providers are therefore trusted in-process components. An
untrusted or external provider must be wrapped in an adapter that redacts
what it may see before `collect` runs — the assembler never hands
untrusted code unredacted provenance.

## Design principle

Retrieval is not:

> search everything, then remove what the caller should not see.

Retrieval is:

> establish what the caller is allowed to consider, then rank within that safe candidate set.
