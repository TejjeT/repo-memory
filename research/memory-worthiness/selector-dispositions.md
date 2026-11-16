# Selector's Proposed Dispositions (do not read before labelling)

**Reviewers: stop here until your labels are recorded.** Everything below was
written by the AI assistant that selected the candidates. These are
model-generated guesses for reviewers to challenge afterwards. They are not
human judgments and do not count toward agreement.

## Candidates from this repository (RM-C1 to RM-C6)

Moved verbatim from `candidates.md` on 2026-11-16.

### RM-C1

**Proposed disposition (selector, not a human label):** *keep*, plus add a
checklist item. It is datable, consequential, missed once and not enforced.
Caveat: a single maintainer, so this is a within-person lapse, not cross-team
rediscovery.

### RM-C2

**Proposed disposition (selector):** *uncertain*. Strong evidence of a stale
window, but the cheaper fix (document hygiene) is now in flight. It becomes
*do-not-keep* if docs stay consistent after PR #34.

### RM-C3

**Proposed disposition (selector):** *keep* for the procedural
(fresh-history) part, *do-not-keep* for the receipt part, which should
become shared code instead. Reviewers may reasonably label the whole thing
*uncertain*.

### RM-C4

**Proposed disposition (selector):** *do-not-keep*. Enforcement already
covers it, and memory would duplicate the tests.

### RM-C5

**Proposed disposition (selector):** *do-not-keep*. Repository instructions
already deliver it. Adding an import test would be the better hardening.

### RM-C6

**Proposed disposition (selector):** *do-not-keep*. A textbook live-retrieval
fact, included as a negative control.

## Summary for RM-C1 to RM-C6

| ID | Kind | Real learned → missed/stale → corrected timeline? | Cheaper alternative | Selector's proposed disposition | Feed to #33? |
|---|---|---|---|---|---|
| RM-C1 | Process lesson | Yes: 10-04 → 10-07 → 10-16 | Checklist / partial lint | keep | **Yes**: reuse/rediscovery |
| RM-C2 | Architecture decision | Yes: 10-03 → stale ≥32 days → PR #34 | Document hygiene | uncertain | **Yes**: freshness/propagation |
| RM-C3 | Evaluation protocol | Yes: 10-04 → 10-08 → 10-09 | Shared code (partly) | keep (procedural part) | **Yes**: reuse, with overlap caveat |
| RM-C4 | Fixed defect | No | Regression tests | do-not-keep | Negative control |
| RM-C5 | Architecture boundary | No | `AGENTS.md` (+ import test) | do-not-keep | Negative control |
| RM-C6 | Config fact | No | `pyproject.toml` | do-not-keep | Negative control |

Balance: three plausible keeps or uncertains, three expected do-not-keeps.

### Implications for the #33 protocol

- **RM-C1 and RM-C3** support a *reuse* test: give an agent the task "set up
  a new experiment fixture/runner" at a revision after the lesson and before
  its re-application, with and without the lesson available. Then compare
  against a well-configured search over the same repository. The tie-breaker
  is whether ordinary search surfaces the lesson *unprompted*.
- **RM-C2** supports a *freshness* test: at a revision inside the stale
  window, ask an architecture question and score whether the answer follows
  `v0-scope.md` or the stale ROADMAP. Repeat after PR #34 merges. If both
  paths pass after the fix, document hygiene was the adequate answer.
- **RM-C4 to RM-C6** should show no benefit. If memory "wins" on them, the
  protocol is biased.
- Every case comes from one repository and one maintainer. None measures
  cross-team waiting. #33 must say so, or add cases from other sources.

### Not yet done (remaining #8 exit criteria)

- [ ] Reviewers agree on and freeze the annotation guide.
- [ ] Expand to about 20 candidates, including permitted sources beyond this
      repository.
- [ ] Two or more independent human reviewers label the same sample.
- [ ] Report agreement, disagreements and adjudication.
- [ ] Mark which retained facts feed #33 (preliminary marking above).

## Candidates from outside this repository (RM-E1 to RM-E14)

Written 2026-11-16. Reasons are one line each on purpose.

| ID | Selector's guess | Reason |
|---|---|---|
| RM-E1 | do-not-keep | Single obvious living document; largely enforced by linters |
| RM-E2 | uncertain | Old record still reads `Final`; only a header link shows the replacement. Low consequence today |
| RM-E3 | do-not-keep | Cleanly marked and enforced by tooling |
| RM-E4 | keep (the exceptions, not the policy) | The policy is easy to find; which changes hold an exception is not |
| RM-E5 | do-not-keep | Time-bound; warnings and then import failure make it self-announcing |
| RM-E6 | keep | A reversed decision; older material still presents the abandoned plan as the future |
| RM-E7 | uncertain | Enforced by the installer, but the authoritative text moved and the permitted workarounds are not obvious |
| RM-E8 | uncertain | Config shows the outcome; the reason is in the ADR; broken back-link |
| RM-E9 | keep | Rejected approach with incident evidence; code shows only the current choice |
| RM-E10 | keep | Manual, out-of-band exception with an end condition and no expiry; invisible in code |
| RM-E11 | keep | Operational procedure around the code, derived from instability |
| RM-E12 | do-not-keep | Readable directly from cluster configuration |
| RM-E13 | keep | Rejected approach; the code cannot show that it was tried and why it failed |
| RM-E14 | do-not-keep | Absence in code is sufficient; low consequence |

Selector's count: 6 keep, 5 do-not-keep, 3 uncertain. The selector knew the
project's thesis when choosing, so this balance is itself a selection effect.
