# Delivery ablation: which semantics reduce to metadata filtering?

Run date: 2026-11-10. **Synthetic, deterministic, model-free.** No agent or
LLM is involved. Full tables: [results/RESULTS.md](results/RESULTS.md).
Raw counts: [results/results.json](results/results.json).

## Why this exists

The #5/#32 agent trials tied (documents 3/3, repo-memory 3/3) because both arms
were handed the complete permitted corpus. That says nothing about what reaches
an agent when context has to be *selected* from a larger store. It also left an
uncomfortable question unanswered, which matters before any paper or patent
effort:

> How much of repo-memory's deterministic resolution can a competently
> configured ordinary index reproduce with flat metadata filters alone, and
> what is left over?

This experiment executes the tests proposed for Gap 4 and Gap 5 in
[gap-analysis.md](../../gap-analysis.md) (TTL / latest-wins / explicit
supersession; authorization before ranking).

## Design

`ablation.py` generates an organization (domains → systems → repositories),
40 policy topics, and for each topic a set of governance units containing:

- a rule with 1–3 revisions. Old revisions are either marked `superseded`
  ("flipped") or left `approved` with only the successor's `supersedes` link
  ("unflipped", the stale-document situation seen with `ROADMAP.md`);
- repository exceptions overriding the current revision: active, expired,
  not yet effective, or still proposed;
- optional complementary constraints at a narrower scope that add to the rule
  without overriding it;
- optional explicit cross-system `applies_to` targets;
- 15% of assertions restricted; half of the callers lack clearance.

Each query is (repository, topic, caller). The **required set** is recorded by
the generator while it builds each unit. It is never computed by
`repo_memory.policy`, so the engine is being checked, not echoed.

Every system delivers at most *k* assertions, ranked by the same BM25 scorer.
Only the candidate set differs:

| System | Candidate set |
|---|---|
| L0 | everything; scope words go in the text query |
| L1 | + ACL prefilter |
| L2 | + `status = approved` |
| L3 | + effective/expiry date range |
| L4 | + scope-ancestry filter and explicit targets (structural scope) |
| L5 | L4, then keep only the newest assertion per topic tag ("latest wins") |
| RM without relations | `resolve_assertions` with supersession and override links blanked |
| RM supersession only / overrides only | one relation family restored |
| RM full | `resolve_assertions` as shipped |

L1–L4 are filters any metadata-capable index supports. They are implemented
independently of `policy.py`; a test asserts that L4 and "RM without relations"
deliver identical results, which cross-checks both implementations.
L5 needs a curated topic tag, which the Engineering Assertion schema does not
have.

Outcomes per query:

- **clean**: every required assertion and no other same-topic assertion.
- **needs-resolution**: every required assertion, plus non-governing same-topic
  ones (stale revision, overridden rule). The reader must still work out
  precedence.
- **missed**: a required assertion is absent; nothing contradictory delivered.
- **misleading**: a required assertion is absent (or none exists) and a
  non-governing same-topic assertion was delivered.

## Results (16 systems, k = 5, mean of 5 seeds, 2000 queries)

Queries whose governing assertion is hidden from the caller (125) are excluded
here and reported below.

| System | clean % | needs-resolution % | missed % | misleading % |
|---|---|---|---|---|
| L0 lexical top-k | 43.4 | 18.2 | 13.4 | 25.0 |
| L1 +ACL prefilter | 44.3 | 18.4 | 14.7 | 22.6 |
| L2 +status=approved | 47.3 | 17.8 | 15.5 | 19.5 |
| L3 +effective/expiry dates | 49.1 | 18.1 | 20.3 | 12.6 |
| L4 +scope ancestry/targets | 79.0 | 21.0 | 0.0 | 0.0 |
| L5 L4 +latest-wins per topic tag | 96.8 | 0.0 | 3.2 | 0.0 |
| RM without relations | 79.0 | 21.0 | 0.0 | 0.0 |
| RM supersession only | 89.1 | 10.9 | 0.0 | 0.0 |
| RM overrides only | 85.6 | 14.4 | 0.0 | 0.0 |
| RM full (policy.py) | 97.2 | 2.8 | 0.0 | 0.0 |

L4 and above are flat across 4, 16 and 64 systems (196–3397 assertions) and
across k = 3, 5, 10. L0–L3 do not recover at any scale or budget: misleading
deliveries stay between 12.6% and 33.3%.
L0 delivered an unauthorized assertion in 630 of 2000 queries; every other
system delivered none.

## What the data shows

1. **Structural scope is the large step, and it is commodity.** Going from
   L3 to L4 removes every missed and misleading delivery. Text-only scope
   (L0–L3) cannot separate sibling systems or reach explicit cross-system
   targets (100% missed). A hierarchical scope filter is ordinary metadata
   filtering; it is not a novel mechanism.
2. **A fully filtered ordinary index equals repo-memory minus relations.**
   L4 and "RM without relations" have identical outcome counts in every
   configuration (10,000 query runs), and identical deliveries in the test.
   Authorization-first, lifecycle and scope semantics add no delivery
   difference over a well-configured filter stack.
3. **Relation-following is the only increment, and its effect is to remove
   distractors, not to recover lost guidance.** At L4 the governing assertion
   is always present; 21% of queries also carry a stale revision or an
   overridden rule. Supersession and override links cut that to 2.8%. In
   #32, agents given the complete documents resolved exactly this kind of
   precedence 3/3. Whether the remaining distractors cause agent errors at
   scale is **not** measured here.
4. **"Topic tag + latest wins" ties the full engine overall, with a different
   failure.** L5 is 96.8% clean against 97.2%. It fails silently: it drops
   every complementary constraint (100% missed in that case), because the
   newest assertion is not the only one that applies. The engine fails
   visibly instead (extra assertions delivered). L5 also benefits from a
   generator property: exceptions are always newer than the rule they
   override.
5. **Two gaps in the shipped engine semantics** (decisions for the
   maintainer; nothing was changed):
   - *Broken chain.* If revision 1 is still `approved`, revision 2 is
     `superseded` and revision 3 is current, nothing active names revision 1,
     so it is returned as active next to revision 3 (92.8% needs-resolution
     in that case). Supersession is not transitive across inactive links.
     L5 handles this case (95.6% clean).
   - *Hidden successor.* Because authorization runs before supersession, a
     successor the caller cannot see does not suppress its visible
     predecessor. The caller receives stale guidance as active (93.3%
     needs-resolution in that case; n = 13).
6. **Authorization-first has a staleness cost for every system.** When the
   governing assertion is hidden from the caller, all authorization-first
   systems, repo-memory included, still deliver a non-governing same-topic
   assertion in about 38–39% of those queries (the base rule when the
   exception is hidden, or an unflipped predecessor when the current rule is
   hidden). Suppressing it would reveal that something hidden exists. This is
   a real trade-off between non-interference and freshness that the current
   documents do not discuss.

## Limits

- **Synthetic by construction.** Case frequencies (30% unflipped revisions,
  25% exceptions, 30% complements, 15% restricted) are parameters, not
  observations. The per-case tables in `RESULTS.md` are more meaningful than
  the blended headline, because the blend follows the parameters.
- **repo-memory's score is partly conformance.** The generator uses the same
  relation vocabulary the engine implements. The informative results are the
  ladder position where ordinary filtering ties (L4), the L5 tie, and the
  engine's own failures.
- **Lexical ranking over templated text.** BM25 on generated sentences is
  not an embedding retriever over real documents. Real text would make
  topic matching harder for every system.
- **Delivery is not outcome.** "needs-resolution" is not an error. No claim
  is made about agent correctness, time or cost.
- **Not preregistered.** The first run exposed a harness artefact (scope words
  in the text query outranked the topic for every system, repo-memory
  included). The query construction was changed so that systems with a
  structural scope filter rank by topic only. Results before that fix were
  discarded and are not reported. The `hidden-successor` tag was added after
  inspecting repo-memory's non-clean outcomes.
- Modelled gaps: a rule revised *after* an exception was granted, declared
  conflicts, revalidation, and human capture cost are not generated.

## Reproduce

```bash
python research/experiments/delivery-ablation/ablation.py /tmp/delivery-ablation
diff -r /tmp/delivery-ablation research/experiments/delivery-ablation/results
```

Takes about 90 seconds. Output is deterministic for a given Python version's
`random` module (generated with Python 3.13).
