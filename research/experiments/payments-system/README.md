# Experiment: Multi-Repository Payments System

Status: design baseline  
Observed/researched: 2026-10-03

## Objective

Test whether durable engineering knowledge requires a dedicated repo-memory service or can be represented cleanly on top of a general context database such as OpenViking.

This experiment deliberately includes context that is:

- not fully recoverable from one repository
- applicable across multiple repositories
- derived from different source systems
- subject to permissions
- capable of becoming stale or superseded

## Fictional system

Organization: `Acme`

Domain: `Payments`

System: `Settlement Platform`

Repositories:

- `payment-api` — public/internal API surface
- `settlement-engine` — settlement processing
- `payment-worker` — asynchronous retries and reconciliation
- `legacy-settlement` — legacy implementation being retired

Teams:

- `payments-platform`
- `settlement-runtime`
- `security-platform`

## Engineering assertions

### EA-001 — Runtime policy

**Type:** organization policy  
**Scope:** Acme / all Java services  
**Content:** New Java services must target Java 25 unless an approved exception exists.  
**Source:** Platform policy `PLAT-JAVA-2026-04`  
**Importance:** high

### EA-002 — Idempotency constraint

**Type:** incident-derived constraint  
**Scope:** Settlement Platform  
**Applies to:** payment-api, settlement-engine, payment-worker  
**Content:** Idempotency keys must survive retries across gateway, queue, and worker boundaries.  
**Reason:** Incident INC-412 demonstrated duplicate settlement when retry metadata was regenerated.  
**Importance:** critical  
**Provenance:** INC-412, ADR-37

### EA-003 — Repository exception

**Type:** approved exception  
**Scope:** legacy-settlement  
**Content:** legacy-settlement remains on Java 17 until retirement milestone M-2027-01.  
**Overrides:** EA-001 for legacy-settlement  
**Source:** Architecture exception EX-93  
**Review after:** 2027-01-15

### EA-004 — API ownership

**Type:** ownership boundary  
**Scope:** Settlement Platform  
**Content:** payments-platform owns the API contract; settlement-runtime owns settlement-engine implementation.  
**Source:** Service catalog records  
**Importance:** medium

### EA-005 — Superseded retry policy

**Type:** engineering rule  
**Scope:** Settlement Platform  
**Content:** Gateway retries may be configured up to three attempts.  
**Status:** superseded  
**Superseded by:** EA-006

### EA-006 — Current retry policy

**Type:** incident-derived constraint  
**Scope:** Settlement Platform  
**Content:** Retry must exist at exactly one orchestration layer for settlement submission; gateway and client retries must not both be enabled.  
**Effective from:** 2026-06-12  
**Source:** INC-463 + ADR-41  
**Supersedes:** EA-005

## Access model

### Alice

Team: payments-platform

Access:
- payment-api
- settlement-engine
- payment-worker
- platform policies
- Settlement Platform ADRs

No access:
- confidential security incident details

Expected behavior:
- may retrieve EA-001 through EA-006
- incident-derived assertions may expose approved engineering conclusions without leaking restricted incident detail

### Bob

Team: external-integrations

Access:
- payment-api only

Expected behavior:
- receives API-facing constraints relevant to payment-api
- must not discover internal settlement-engine-only details
- must not learn the existence of restricted incident material if policy prohibits it

### Carol

Team: security-platform

Access:
- all listed repositories
- security findings
- incidents

Expected behavior:
- may retrieve all assertions plus full permitted provenance

## Test questions

### T1 — Cross-repository task

Task:

> Update payment-worker retry handling.

Expected required context:
- EA-002
- EA-006

A repository-only agent should not reliably infer the full incident-derived rationale.

### T2 — Policy + exception

Task:

> Upgrade legacy-settlement runtime.

Expected context:
- EA-001
- EA-003

Correct outcome:
- do not blindly upgrade to Java 25
- surface the approved exception and review date

### T3 — Supersession

Task:

> Add gateway retry for settlement calls.

Expected context:
- EA-006 active
- EA-005 historical/superseded

Incorrect behavior:
- returning EA-005 as current guidance without its superseded status

### T4 — Authorization

Bob asks:

> Why does settlement-engine prohibit retries?

Expected behavior:
- retrieval must respect Bob's scope/access
- inaccessible evidence or internal assertions must not enter the candidate set if policy forbids disclosure

### T5 — Provenance

Agent asks:

> Why must idempotency keys survive queue boundaries?

Expected response should provide:
- the durable assertion
- permitted provenance references
- status/freshness
- not merely a semantic similarity result

## Implementations to compare

### A. Native OpenViking model

Represent:
- repositories and policies as resources
- shared engineering assertions as shared resources or custom context
- ACLs through resource hierarchy
- session-derived memory only where useful

### B. repo-memory contract on OpenViking

Use OpenViking for:
- storage
- indexing
- retrieval
- ACL infrastructure

Add repo-memory semantics:
- engineering assertion schema
- explicit applicability
- typed provenance
- supersession
- effective/review dates
- source authorization references

### C. Standalone repo-memory

Implement the same behavior using a dedicated metadata store and retrieval layer.

## Evaluation dimensions

Score each implementation on:

1. expressiveness
2. source-aligned authorization
3. cross-repository applicability
4. provenance fidelity
5. lifecycle and supersession
6. retrieval correctness
7. stale-context risk
8. agent portability
9. implementation complexity
10. operational complexity
11. inspectability
12. evaluation reproducibility

## Decision rule

Prefer the simplest architecture that preserves the required engineering semantics.

A standalone database is justified only if the OpenViking-backed representation materially fails the experiment.
