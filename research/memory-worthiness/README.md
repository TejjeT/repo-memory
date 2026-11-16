# Memory-Worthiness Research (issue #8)

Status (2026-11-04): **first candidate-selection pass. No human labels yet.**

This folder holds:

- [`annotation-guide.md`](annotation-guide.md): the draft guide reviewers use
  to label candidates *keep*, *do-not-keep* or *uncertain*.
- [`candidates.md`](candidates.md): six candidate engineering decisions drawn
  from this repository's own public history, each with source revisions,
  scope, current vs historical guidance, retrieval access and the timing
  evidence available for #33.

## What this pass is and is not

It **is** the "small next contribution" in #8: real, permitted, source-backed
candidates selected to inform #33's timing protocol, deliberately including
cases that favor ordinary retrieval or another fix (tests, lint, shared code).

It is **not** completion of #8:

- Every "proposed disposition" in `candidates.md` was written by the AI
  assistant that selected the candidates. These are a hypothesis for reviewers
  to challenge, **not** human judgments. No agreement statistics exist.
- The exit criteria still require at least two independent human reviewers
  labeling the same sample, a reported agreement/adjudication, and a larger
  (~20 candidate) balanced sample.

## Source and its limits

All candidates come from the `TejjeT/repo-memory` repository (commits, PRs,
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
