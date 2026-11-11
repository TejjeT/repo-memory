# Mneme HQ

Observed: 2026-11-11. Source: public repository
[MnemeHQ/mneme](https://github.com/MnemeHQ/mneme) at commit `1575008`
(2026-11-10), package `mneme-hq` 0.11.0, MIT licence.

Read in full or in large part: `README.md`, `docs/adr/ADR-031` (decision
governance semantics), `docs/roadmap/README.md` (DG1, DG2, enterprise
boundary), the header of `mneme/decision_waiver_authority.py`. Everything else
was surveyed by file listing and keyword search only. The code was not run.

## Documented behavior

- **Positioning.** "An open decision and control layer for agentic software
  development." Turns durable engineering decisions and ADRs into agent
  context and deterministic enforcement. States it is not a vector store or
  conversational memory.
- **Determinism.** Same input and decision state give the same verdict; no LLM
  judge for allow/warn/fail. Retrieval relevance is explicitly kept separate
  from enforcement applicability (ADR-017, ADR-031 §4).
- **Authority store.** One repository-local file,
  `.mneme/project_memory.json`, with immutable decision versions, an
  active-version pointer and explicit `supersedes` relationships (ADR-030).
- **Precedence.** Accepted status, then explicit supersession, then
  author-supplied priority within an exact same-scope group. Ties are reported
  as ambiguity, never guessed. Date is being removed as a tie-breaker
  (ADR-031 §2).
- **Resolution.** A single resolver, `resolve_effective(state, context)`, with
  a trace of why a decision is not effective, and `resolve_change` between two
  snapshots (ADR-031 §1, §9). Context carries paths, an explicit `as_of`
  instant and opaque labels.
- **Exceptions.** Canonical waivers with requester/approver claims, written
  only by explicit CLI commands. As of this commit they have no runtime
  consumer (module header, charter dated 2026-11-10).
- **Enforcement surfaces.** Pre-change hooks for several coding agents, a
  post-change audit, and a CI gate. Integrations are listed with evidence
  levels.
- **MCP.** Six tools: propose and read only. Accept, supersede, waive and
  bypass are deliberately not exposed (ADR-027).
- **Identity and access.** `labels` "carry no identity, team, role, directory
  or organization meaning. RBAC, SSO, directory authority and enterprise
  policy stay outside DG1" (ADR-031 §6). Identity fields are recorded as
  unauthenticated claims.
- **Roadmap.** DG2 "deterministic decision federation": declared
  organization-level → platform/domain → repository decisions → authorized
  exception, across repositories at pinned revisions. Not implemented at this
  commit. Organization-wide identity, discovery and hosted governance are
  placed outside the open-source core.
- **Evidence sought, per roadmap:** design-partner pilots measuring
  first-attempt compliance and retention. No controlled agent-outcome
  comparison against a retrieval baseline was found by keyword search.

## Interpretation

Mneme occupies repo-memory's thesis and is further along as a product: about
46,000 lines of Python, enforcement hooks, governed writes, a change resolver
and evidence identity. Commit history shows a single author.

| Dimension | Mneme (this commit) | repo-memory |
|---|---|---|
| Deterministic resolution, no LLM precedence | Yes | Yes |
| Explicit supersession, history kept | Yes | Yes |
| Exceptions | Waivers recorded, not yet consumed | Exceptions that name the rule they override, consumed at read time |
| Scope | One repository; paths and exact scope strings | Organization → domain → system → repository, plus explicit cross-system targets |
| Cross-repository hierarchy | Roadmap (DG2) | Implemented in the reference resolver |
| Authorization before resolution, provenance redaction | Explicitly out of scope | Implemented and tested |
| Governed writes (propose, accept, supersede) | Yes | Not implemented (#3) |
| Enforcement at edit time and in CI | Yes | None |
| Agent integrations | Several | Read-only MCP reference |
| Controlled agent trials against retrieval baselines | Not found | Yes: ties, recorded with receipts |
| Analysis of which semantics reduce to metadata filtering | Not found | [Delivery ablation](../experiments/delivery-ablation/README.md) |

Consequences for repo-memory:

1. **Do not build a competing product.** The enforcement wedge, receipts
   ("evidence identity"), exception records and change impact are built or
   publicly planned there.
2. **The hierarchy is not a durable differentiator.** It is Mneme's stated
   next step and is already described in public.
3. **Two things remain distinct:** authorization-aware resolution (what a
   caller with partial visibility should receive), which Mneme excludes from
   its core, and independent measurement of whether any of this changes agent
   outcomes.
4. **Prior art.** Mneme's dated public ADRs and roadmap cover deterministic
   precedence, supersession, time-bound waivers and hierarchical federation.
   This further weakens any broad patent claim.

Not verified: how complete each Mneme feature is in practice, its benchmark
contents, and whether a private or hosted offering exists.
