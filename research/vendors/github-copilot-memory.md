# GitHub Copilot Memory

Observed: 2026-10-03  
Status: public preview

## Why this matters

GitHub Copilot Memory is the closest direct industry benchmark for learned repository memory.

Any repo-memory design should assume this capability exists and avoid merely reproducing it.

## Documented memory types

### Repository-level facts

Examples documented by GitHub include:

- coding conventions
- architectural decisions
- build commands
- project-specific rules

Facts are shared with users who have Copilot Memory access for that repository.

### User-level preferences

Preferences represent implied or explicit interaction preferences and can apply across repositories for that user.

## Creation

Repository facts are created only in response to Copilot activity initiated by users who:

- have write access to the repository
- have Copilot Memory enabled

The public documentation does not expose the extraction model or exact fact-selection algorithm.

## Provenance and validation

This is the strongest part of the design.

Repository facts are stored with citations pointing to supporting code.

When a memory becomes relevant, Copilot checks those citations against the current branch before use. Only validated facts are used.

This also protects against facts learned from unmerged/closed pull requests: the fact does not affect behavior unless the current codebase still supports it.

## Scope

Repository facts may only be used for operations on the same repository.

This is a deliberate privacy/security boundary.

User preferences are cross-repository but are user-specific rather than organization engineering knowledge.

## Retention

Unused stored facts/preferences are automatically deleted after 28 days.

The timer may reset after successful validation/use.

### Interpretation

GitHub appears to optimize memory as a fresh working set rather than permanent institutional knowledge.

That is a very reasonable choice for automatically inferred facts.

It may be insufficient for engineering knowledge that must remain available even when infrequently used, such as disaster-recovery constraints, rare migration rules, or architectural exceptions.

That is an inference, not a documented GitHub limitation.

## Governance

Repository owners can inspect and delete repository facts.

Organization/enterprise administrators can:

- enable/disable the feature by policy
- export user-level preferences
- delete user-level preferences
- see audit events for administrative memory actions and opt-out events

Public docs do not describe:
- approving individual repository facts before creation
- editing a repository fact
- explicit supersession relationships
- manual cross-repo applicability

## Cross-surface reuse

GitHub documents Copilot Memory use across:

- Copilot cloud agent
- Copilot code review
- Copilot CLI
- agentic autofix

This proves the value of a shared memory backend across multiple agent experiences.

## Benchmark profile

Primary unit:
- repository fact
- user preference

Scope:
- repository
- user

Cross-repo:
- repo facts: no
- user preference: yes, but personal

Provenance:
- code citations for repository facts

Freshness:
- current-branch validation
- 28-day unused TTL

Contradictions:
- no explicit documented model

Authorization:
- repository access
- Copilot policy
- user write permission constrains creation

Human governance:
- inspect/delete
- organizational policy control

Creation:
- automatic from Copilot activity

Retrieval:
- product-managed

Interoperability:
- GitHub Copilot surfaces only

Portability:
- vendor-managed

Auditability:
- administrative actions have audit-log coverage
- details of per-use memory audit are not publicly documented

## Ideas worth borrowing

1. **Evidence-bound facts**
2. **Validate before use**
3. **Aggressive freshness for auto-generated knowledge**
4. **Shared backend across multiple coding-agent experiences**
5. **Simple repository-admin visibility**

## Research questions still open

- How does GitHub decide that a discovery is worth storing?
- What exact form do repository citations take internally?
- Are multiple citations supported per fact?
- How are contradictions handled?
- Is relevance ranking semantic, symbolic, or hybrid?
- Is memory usage visible in agent traces?
- Will GitHub eventually add organization/system memory?

## Sources

- https://docs.github.com/en/copilot/concepts/agents/copilot-memory
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/copilot-memory/manage-as-administrator
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/copilot-memory/manage-for-yourself
