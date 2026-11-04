# Annotation Guide: Is This Worth Keeping as Durable Engineering Memory?

Draft v0.1, 2026-11-04 (issue #8). Reviewers should propose edits before
labeling begins; freeze the version used and record it with each label.

## The question

> Is this durable engineering context difficult or costly to reconstruct
> from the current source of truth, and is it likely to materially improve a
> future engineering decision?
> — `AGENTS.md`

If the answer is no, prefer live retrieval (reading the code, tests, config,
docs or issue tracker at the time of need) over persistent memory.

## Labels

| Label | Use when |
|---|---|
| **keep** | All four criteria below hold, and retaining it as a scoped, provenance-backed assertion is better than every cheaper alternative listed under "Alternatives". |
| **do-not-keep** | Any criterion clearly fails, **or** a cheaper alternative already makes it reliably discoverable or enforced. |
| **uncertain** | Evidence is insufficient to decide, or reasonable reviewers could disagree. Say what evidence would decide it. |

`uncertain` is a legitimate answer. Do not force a decision.

## Criteria

Answer each with *yes*, *no* or *unknown*, and cite the evidence.

1. **Costly to reconstruct.** Can a competent engineer or agent recover this
   from the current source of truth (code, tests, config, current docs) when
   they need it? Evidence of cost: it was missed or rediscovered, it lives only
   in review threads or commit messages, current docs contradict it, or
   recovering it needs restricted or scattered sources.
2. **Actionable and likely to recur.** Will future work plausibly hit a
   decision point where this changes what someone does?
3. **Identifiable scope, provenance and stability.** Can you name where it
   applies (organization / system / repository / component), cite the source
   that established it, and expect it to stay true long enough to be worth
   maintaining?
4. **Consequential if missed.** What goes wrong without it, compared with the
   cost of capturing, approving, refreshing and permissioning it?

## Alternatives to check before choosing *keep*

- **Already enforced:** a test, type, lint rule or CI check fails if the rule
  is violated. Enforcement usually beats memory.
- **Already loaded:** repository instruction files (`AGENTS.md`, `CLAUDE.md`)
  or equivalent that every agent session reads.
- **Single obvious current document**, found reliably by ordinary search,
  with no conflicting older document.
- **Better fixed in code:** shared library, template or fixture generator
  that makes the mistake impossible.

If an alternative is adequate, label *do-not-keep* and name it. If the right
answer is "add the test/lint instead", say so; that is a useful outcome.

## Required metadata per label

- Candidate ID and guide version
- Reviewer (pseudonymous ID is fine) and date
- Label and per-criterion answers with cited evidence
- Proposed scope, if keep
- Which alternative applies, if do-not-keep
- What evidence would change the label, if uncertain
- Free-text notes

## Rules

- Label independently. Do not view other reviewers' labels or the
  selector's proposed disposition until after labeling. Hide the "Proposed
  disposition" sections in `candidates.md` from reviewers.
- Model-generated labels are not human judgments and are not counted toward
  agreement.
- Do not add facts that are not in the cited sources. Missing timing or
  effort data stays *unknown*.
- Restricted material (incident details, private repositories) must not enter
  the public dataset; record that a restricted source exists and redact it.

## Reporting (after labeling)

Report per-candidate labels, raw agreement and a chance-corrected statistic
appropriate for the number of reviewers, every disagreement with each side's
reasoning, and the adjudicated outcome. Keep uncertain and do-not-keep cases
in the published set.
