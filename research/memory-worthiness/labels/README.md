# Labelling

Issue #8. **No human labels exist yet.**

## For a reviewer

1. Read [`../annotation-guide.md`](../annotation-guide.md). Propose edits
   before you start; record the guide version you used.
2. Copy `TEMPLATE.csv` to `<your-reviewer-id>.csv` (a pseudonym is fine).
3. Label the 20 candidates **in the order the file lists them** (the order is
   shuffled with seed 20261116 so the two sources are mixed). Read each
   candidate in [`../candidates.md`](../candidates.md) (RM-C…) or
   [`../candidates-external.md`](../candidates-external.md) (RM-E…).
4. `label` must be `keep`, `do-not-keep` or `uncertain`. Answer the four
   criterion columns with `yes`, `no` or `unknown`. Fill the remaining columns
   as the guide's "Required metadata" section asks.
5. **Do not open [`../selector-dispositions.md`](../selector-dispositions.md)
   or another reviewer's file until your labels are committed.**

Expect roughly five minutes per candidate.

## Known blinding limits

- RM-C1 to RM-C6 were published with the selector's proposed labels inline
  from 2026-11-04 (PR #35) until they were moved on 2026-11-16. A reviewer who
  read the earlier version has seen those guesses. Record that in `notes`.
- The RM-C entries still contain "Alternatives" and "Timing data for #33"
  paragraphs written by the selector, which hint at its view. The RM-E entries
  were written without such paragraphs.
- The selector chose all 20 candidates knowing the project's thesis.

## After two or more reviewers have labelled

```bash
python research/memory-worthiness/labels/agreement.py \
  research/memory-worthiness/labels/<r1>.csv research/memory-worthiness/labels/<r2>.csv
```

This prints raw agreement, Cohen's kappa and every disagreement. With one
reviewer there is nothing to compute, and no agreement figure may be reported.
Adjudication is then written up by hand, keeping uncertain and do-not-keep
cases in the published set.
