# Benchmark: GitHub Copilot Memory vs OpenViking vs repo-memory

Observed: 2026-10-03

Status: working research baseline. "repo-memory" columns describe the current proposed design, not implemented capability.

## Executive summary

The comparison suggests that repo-memory should **not** position itself as "persistent memory for coding agents." Both GitHub Copilot Memory and OpenViking already cover substantial parts of that problem.

The potentially interesting space is narrower and more engineering-specific:

> An open engineering-memory contract for durable context that spans repository, system, domain, and organization boundaries, while preserving source provenance, authorization, lifecycle, and agent portability.

The strongest existing benchmarks are complementary:

- **GitHub Copilot Memory** is strongest as native repository memory integrated into GitHub/Copilot workflows, especially its code citations, current-branch validation, repository scoping, and operational simplicity.
- **OpenViking** is strongest as a general agent context database: resources + memory + skills, hierarchical filesystem-style context, cross-agent integrations, session extraction, progressive retrieval, and explicit server authentication/ACL capabilities.
- **repo-memory**, if built, needs to justify itself through engineering semantics neither benchmark makes first-class: system/domain hierarchy, typed engineering provenance, cross-repository applicability, explicit supersession/contradiction semantics, and evaluation against engineering outcomes.

## Comparison matrix

| Dimension | GitHub Copilot Memory | OpenViking | repo-memory hypothesis |
| --- | --- | --- | --- |
| Primary abstraction | repository facts + user preferences | resources + memories + skills | durable engineering assertions |
| Repository awareness | first-class | repository is a resource; memories are general context | first-class |
| Scope | repository + user preference | account/user/peer/path/resource hierarchy | organization → domain → system → repo → component → PR |
| Cross-repository memory | repository facts constrained to same repo | possible through shared resources/namespaces/context | explicit applicability/inheritance |
| Engineering system/application scope | not documented as first-class | can be modeled through paths/resources, not engineering-native | first-class |
| Provenance | code citations for repo facts | context/resource references and session provenance available; general memory is filesystem content | typed provenance: commit/PR/ADR/incident/catalog/policy/etc. |
| Revalidation | code citations checked against current branch | resources can be updated; memory extraction/consolidation supported | source-revision validation + review/expiry |
| Retention | unused memories auto-delete after 28 days | long-term, dynamically updated; user controls and policies | configurable lifecycle, no universal TTL |
| Supersession | not documented as explicit relationship | merge/edit/delete/consolidation semantics | explicit superseded-by / effective dates |
| Contradictions | not documented as first-class | consolidation/update policies may reconcile memories | explicit conflict state and resolution rules |
| Creation | generated from Copilot activity | sessions, explicit remember, resource ingestion | agent/human/event proposal pipeline |
| Human approval | repository facts can be reviewed/deleted; creation approval not described | explicit writes; integrations/policies vary | policy-based proposal/approval workflow |
| Human inspection | repository owners/admins can inspect facts | filesystem-style browse/read/edit | required |
| Authorization | repository access + Copilot policies | account/user roles, groups, resource ACLs, OIDC/LDAP/API-key/trusted modes | source-aligned scope authorization |
| Retrieval | Copilot-managed | semantic + directory traversal + read/find/search | authorize/filter first, hybrid rank second |
| Progressive context | product-managed | L0/L1/L2 summaries and on-demand detail | task-budgeted context assembly |
| Agent interoperability | Copilot surfaces | broad: MCP and multiple agent runtimes/frameworks | vendor-neutral MCP/API/schema |
| Portability | GitHub/Copilot-owned | self-hostable open-source context store | open schema + export |
| Auditability | admin memory export/delete audit events; repo facts review | observable retrieval trajectories + filesystem state; auth/admin controls | full creation/approval/use/validation lineage |
| Evaluation focus | product effectiveness; no public repo-memory benchmark known | publishes memory/context evaluations | engineering task outcome benchmark |
| Best current strength | source-backed repo facts with validation | general-purpose context architecture + interoperability | engineering semantics, if validated |

## Detailed observations

### 1. GitHub Copilot Memory is a serious direct benchmark

GitHub documents two memory classes:

- repository-level facts such as coding conventions, architecture decisions, build commands, and project rules
- user-level preferences across repositories

Repository facts are stored with citations to supporting code. When a fact is relevant, Copilot validates its citations against the current branch and only uses validated facts.

Repository facts can only be used for operations on the same repository. They are created in response to Copilot activity initiated by users with write access and memory enabled.

Unused facts/preferences are deleted after 28 days; successful validation/use can reset that timer.

Repository owners can inspect and delete repository facts. Organization/enterprise administrators can control the feature and audit administrative memory operations.

### Implication

A repo-memory MVP that only extracts facts from code/PR activity into a vector database would be materially behind this benchmark.

The strongest idea to borrow is **source-backed revalidation**.

---

### 2. OpenViking is closer to a context operating system

OpenViking deliberately separates:

- resources: documents, repositories, reference material
- memories: preferences, entities, events, experience extracted from sessions or explicitly recorded
- skills: reusable task instructions and supporting resources

All are represented in a virtual filesystem under viking URIs.

OpenViking uses layered context:
- L0 abstract
- L1 overview
- L2 original detail

Retrieval combines semantic matching with directory traversal, giving it a hierarchy-aware context-selection model rather than a flat vector namespace.

Its integrations support multiple coding agents and MCP clients.

### Implication

repo-memory should not claim hierarchy, progressive disclosure, or cross-agent integration as unique ideas. OpenViking already has credible implementations of all three.

---

### 3. OpenViking authorization is more mature than expected

OpenViking supports:

- API-key authentication
- OIDC
- LDAP
- trusted-gateway identity
- account/user roles
- groups
- per-resource ACLs
- separate read/write/manage permissions

This means "permission-aware remote context" alone is also not sufficient differentiation.

### Remaining question

OpenViking's authorization is primarily a **context-store authorization model**.

repo-memory should investigate a stricter **source-aligned engineering authorization model**:

> If memory derives from GitHub repo A, incident system B, or architecture document C, does eligibility automatically track access to the underlying source and its engineering scope?

This is a narrower problem than generic RBAC/ACL.

---

### 4. The most important conceptual difference may be "resource vs engineering memory"

In OpenViking, repositories are resources. Memory is primarily extracted from sessions into user/peer memory types such as profile, preferences, entities, events, cases, trajectories, and experiences.

That is powerful general agent memory.

But an engineering organization may want a durable object such as:

> "All consumers of payment-api v3 must preserve idempotency keys across retry boundaries because incident INC-412 showed duplicate settlement risk."

That object is not merely:
- a document,
- a user preference,
- a session summary,
- or a repository fact.

It has:
- engineering scope
- applicability across several repos
- typed provenance
- an owning team
- effective dates
- consequence if missed
- possibly a replacement/supersession relationship

### Hypothesis

This "engineering assertion" is the most promising core abstraction for repo-memory.

---

### 5. Lifecycle semantics differ significantly

#### GitHub
Uses validation plus a 28-day unused-memory TTL.

This is elegant for automatically learned working knowledge.

#### OpenViking
Uses persistent memories that can be dynamically updated, merged, deleted, or consolidated through memory policies and extraction.

This is suitable for general evolving agent context.

#### repo-memory opportunity
Some engineering knowledge needs a more formal temporal model:

- approved at
- effective from
- review after
- expires at
- superseded by
- conflicts with
- source revision
- applicability conditions

The key question is whether this complexity creates actual downstream value.

---

## What we should borrow

### From GitHub Copilot Memory

1. Source citations are mandatory for learned engineering facts where possible.
2. Revalidate against current source before using a memory.
3. Make repository-memory inspection simple.
4. Keep automatically learned facts aggressively fresh.
5. Do not assume every memory needs indefinite retention.

### From OpenViking

1. Separate resources from learned memory.
2. Use hierarchy before semantic ranking.
3. Progressive context loading beats dumping everything into prompts.
4. Make retrieval observable.
5. Keep memory vendor-neutral.
6. Support explicit as well as automatic memory creation.
7. Treat authentication/ACL as infrastructure, not an afterthought.

## What repo-memory should test rather than assume

### Hypothesis A — Engineering hierarchy adds value

Can explicit organization/domain/system/repository scope outperform generic folders/namespaces?

### Hypothesis B — Typed engineering provenance adds value

Does distinguishing ADR, incident, PR, policy, catalog entity, and security finding improve trust, revalidation, or retrieval?

### Hypothesis C — Cross-repo applicability matters

Do real coding tasks materially improve when an agent retrieves constraints discovered outside the active repository?

### Hypothesis D — Explicit supersession prevents harmful stale context

Does a formal temporal model outperform TTL + source validation for long-lived engineering rules?

### Hypothesis E — Memory-worthiness can be learned

Can we identify which engineering facts deserve persistence without generating excessive noise?

## Recommended product boundary

Do **not** build:
- another generic user-memory service
- another general context database
- another vector-backed repository index
- a replacement for OpenViking

Instead, initially treat repo-memory as an **engineering memory protocol and reference service** that can potentially sit on top of, or integrate with, context stores such as OpenViking.

Conceptually:

    Git / GitHub / ADRs / Incidents / Catalog / Policies
                         |
                         v
                Engineering assertions
          (scope + provenance + lifecycle)
                         |
                repo-memory contract
                         |
          +--------------+---------------+
          |                              |
     OpenViking / DB                direct service
          |                              |
          +--------------+---------------+
                         |
                         v
              coding-agent runtimes

That keeps the project focused on the part that is plausibly differentiated.

## Next benchmark experiments

1. Model one multi-repo application in OpenViking and repo-memory.
2. Represent one incident-derived engineering rule in each.
3. Simulate rule supersession.
4. Simulate a user who can access repo A but not repo B.
5. Test two agent runtimes against the same memory.
6. Compare repo-only vs live-resource retrieval vs durable engineering assertion.

## Sources

Primary documentation reviewed:

GitHub:
- https://docs.github.com/en/copilot/concepts/agents/copilot-memory
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/copilot-memory/manage-as-administrator
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/copilot-memory/manage-for-yourself

OpenViking:
- https://openviking.ai/docs
- https://docs.openviking.ai/en/concepts/02-context-types
- https://docs.openviking.ai/en/guides/04-authentication
- https://docs.openviking.ai/en/concepts/08-session
- https://docs.openviking.ai/en/context-compilation/06-memory-consolidation
- https://github.com/volcengine/OpenViking
