# Publication and Patent Readiness

Assessment date: 2026-11-10. Written by an AI assistant from the repository's
recorded evidence. **Not legal advice and not a prior-art search.** A patent
attorney and a proper search are required before any filing decision.

## Short answer

- **Patent:** weak case today. The mechanisms that the evidence shows are
  doing the work (authorization before ranking, lifecycle and scope filters)
  are established practice, and the one remaining increment
  (relation-following for supersession and overrides) has close analogues.
- **Paper:** a credible *negative-result / measurement* paper is within reach.
  A "durable engineering memory improves agents" paper is not supported by
  the evidence so far.

## What the evidence supports

| Claim | Evidence | Status |
|---|---|---|
| Agents need organizational context that is absent from code | Repo-only arms: Java 0/3, policy routing 0/3 (abstentions) | Supported, small n, synthetic tasks |
| repo-memory beats complete ordinary documents on correctness | #5/#32: 3/3 vs 3/3; #27: memory 2/3 assigned | **Not supported** (ties, one incomplete memory run) |
| Structural scope and authorization-first filtering prevent wrong-scope and unauthorized delivery | [Delivery ablation](experiments/delivery-ablation/README.md): misleading 12.6–33.3% without a scope filter, 0% with | Supported, synthetic, model-free |
| That filtering needs repo-memory | Same ablation: an independent flat filter stack (L4) equals the engine without relations | **Refuted** for delivery |
| Explicit supersession/override links add value beyond filters | Same ablation: 79.0% → 97.2% clean; the difference is distractors removed, never guidance recovered | Supported for delivery only; agent impact unmeasured |
| Explicit links beat "topic tag + latest wins" | 97.2% vs 96.8% clean; different failure modes | **Tie overall** |
| Memory reduces time to correct context, or amortizes across reuse | #33 protocol drafted (PR #36), nothing collected | Untested |
| A memory-worthiness model exists | #8 first pass (PR #35), no human labels | Untested |

## Prior art that constrains novelty

Located by web search on 2026-11-10 and from general knowledge. Only the
search summaries were read, not the full documents; verify each before
relying on it.

- **Policy precedence and conflict handling.** XACML 3.0 defines rule- and
  policy-combining algorithms (deny-overrides, permit-overrides,
  first-applicable, only-one-applicable).
  ([OASIS core spec](https://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-en.html),
  [formalization, arXiv 1206.5327](https://arxiv.org/pdf/1206.5327)).
  Deterministic, explicit precedence over hierarchical targets is decades old.
  *Interpretation:* "exception overrides only the IDs it names" is a specific
  combining rule, not a new category.
- **Temporal validity and non-destructive invalidation in agent memory.**
  Zep/Graphiti keeps superseded facts with validity intervals in a bi-temporal
  graph ([arXiv 2501.13956](https://arxiv.org/abs/2501.13956), January 2025).
  *Interpretation:* "superseded assertions stay inspectable" is anticipated
  for agent memory generally. Their invalidation is LLM-assisted; ours is
  declared. That difference is real but narrow.
- **Supersession as a governed status.** Architecture Decision Records use
  proposed / accepted / deprecated / superseded with bidirectional links, and
  tooling automates it
  ([Fowler](https://www.martinfowler.com/bliki/ArchitectureDecisionRecord.html),
  [Backstage](https://backstage.io/docs/next/architecture-decisions)).
- **Authorization before retrieval.** Described publicly as a design
  principle, including compiling Cedar policy residuals into index filters
  ([Windley, January 2026](https://www.windley.com/archives/2026/01/authorization_before_retrieval_making_rag_safe_by_construction.shtml)).
  Gap 5 in [gap-analysis.md](gap-analysis.md) is therefore known practice.
- **Repository-scoped agent memory with citations and revalidation.** See
  [vendors/github-copilot-memory.md](vendors/github-copilot-memory.md).

What was *not* found in this light pass (absence of evidence only): a typed,
open contract combining engineering scope hierarchy, typed provenance,
declared overrides and supersession, consumed by multiple agent runtimes; and
any published measurement of which of those semantics matter for coding
agents.

## Candidate contributions, ranked by how defensible they are now

1. **Measurement / negative result (strongest).** "When does engineering
   memory help a coding agent beyond retrieval?" Contributions: the
   three-arm protocol with receipts and assigned denominators, the tie under
   complete delivery, and the delivery ablation that locates the tie at a
   flat filter stack and isolates relation-following as the only increment.
   Workshop-paper scale. Needs: real-repository cases (#8), the #33 timing
   run, and an agent experiment at the "needs-resolution" boundary (below).
2. **The authorization–freshness trade-off.** The ablation shows that
   authorization-first resolution delivers stale or overridden guidance when
   the governing assertion is hidden (about 38–39% of such queries), and that
   a hidden successor cannot suppress a visible predecessor. A principled
   treatment (what may be suppressed without revealing hidden state) looks
   like the most original technical thread in the project. Needs: a formal
   statement, a survey of how access-controlled retrieval systems handle it,
   and a proposed semantics with a non-interference argument.
3. **The Engineering Assertion contract as an open specification.** Useful
   and publishable as a spec or experience report. Novelty is in the
   combination and engineering framing, which is weak ground for a patent.
4. **Memory-worthiness model (Gap 6).** Potentially the most valuable, with
   no data yet. Depends entirely on #8's human labels.

## Patent considerations (for discussion with counsel)

- Everything in this repository is **public** (public GitHub repository, MIT
  licence, dated commits from 2026-10-03). Public disclosure starts grace
  periods where they exist (12 months in the US) and is an absolute bar in
  most other jurisdictions. Anything already committed is likely unpatentable
  outside grace-period countries. Confirm with counsel; the earliest relevant
  date matters.
- Claims on scope filtering, lifecycle filtering, authorization-before-ranking
  or deterministic precedence in general would face the prior art above.
- If anything is claimable it would be narrow and not yet built, for example a
  specific mechanism for item 2. **Do not commit such a design to this public
  repository before speaking to counsel** if a filing is intended.
- An honest alternative is defensive publication: publish the measurements
  and the spec, and compete on being the open reference.

## What would change this assessment

1. **Agent experiment at the needs-resolution boundary.** The ablation says
   a filtered index delivers the governing rule plus distractors in 21% of
   queries. Run agents on L4-style delivery vs resolved delivery, at
   realistic distractor counts. If agents err on distractors, relations
   matter for outcomes. If they do not, the adequate product is a filter
   configuration, and that is the finding.
2. **Real cases.** #8 with two human reviewers; candidates from outside this
   repository.
3. **Timing and reuse.** Freeze and run #33.
4. **Decide the two engine gaps** (broken chain, hidden successor) found by
   the ablation.

## Open decisions for the maintainer

- Merge or revise PRs #34, #35, #36. #33 cannot be frozen until then.
- Are two human reviewers available for #8 and for #33's T1/T2 scoring?
- Is a filing actually intended? If yes, talk to counsel before item 2 above
  is designed in public.
