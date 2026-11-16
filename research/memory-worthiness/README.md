# Memory-Worthiness Research (issue #8)

Status (2026-11-16): **20 candidates selected and a blinded labelling packet
prepared. No human labels yet.**

This folder holds:

- [`annotation-guide.md`](annotation-guide.md): the guide reviewers use to
  label candidates *keep*, *do-not-keep* or *uncertain* (draft v0.2).
- [`candidates.md`](candidates.md): six candidates (RM-C1 to RM-C6) from this
  repository's own history.
- [`candidates-external.md`](candidates-external.md): fourteen candidates
  (RM-E1 to RM-E14) from Python PEPs and two public-sector ADR repositories.
- [`labels/`](labels/README.md): instructions, a shuffled label template and a
  script that reports agreement once two reviewers have labelled.
- [`selector-dispositions.md`](selector-dispositions.md): the selecting AI's
  own guesses. **Reviewers open this last.**

## What this pass is and is not

It **is** the "small next contribution" in #8: real, permitted, source-backed
candidates selected to inform #33's timing protocol, deliberately including
cases that favor ordinary retrieval or another fix (tests, lint, shared code).

It is **not** completion of #8:

- Every "proposed disposition" in `candidates.md` was written by the AI
  assistant that selected the candidates. These are a hypothesis for reviewers
  to challenge, **not** human judgments. No agreement statistics exist.
- The exit criteria still require at least two independent human reviewers
  labeling the same sample and a reported agreement/adjudication. The
  ~20-candidate sample now exists (2026-11-16). One reviewer (the maintainer)
  is confirmed; agreement cannot be reported until a second reviewer labels
  the same sample.

## Source and its limits

The RM-E candidates' sources and limits are listed at the top of
[`candidates-external.md`](candidates-external.md).

The RM-C candidates come from the `TejjeT/repo-memory` repository (commits, PRs,
issues and experiment reports up to `8dbe325`, 2026-10-16, plus open PR #34).
This source was chosen because it is public, its provenance is complete and
no restricted material is involved.

Limits that reviewers and #33 must account for:

- **One small research repository, one primary maintainer, AI-assisted
  development.** Decisions here propagate through a few people and agent
  sessions, not across teams. Cross-team discovery cost cannot be measured from
  it.
- **Selection bias.** The selector knew the project's thesis. Reviewers should
  add candidates from other permitted sources (real ADRs, incident reviews,
  migration PRs) before the ~20-item sample is assembled.
- **Timing evidence is commit and report timestamps only.** Actual human
  waiting time, effort and who read what are not recorded and remain
  **unknown**. No delays have been estimated or invented.

## How this feeds #33

`candidates.md` ends with a summary table marking which candidates have a real,
datable "learned → missed or stale → corrected" timeline. Those are the only
ones that can seed a freshness or reuse protocol without synthetic delays.
