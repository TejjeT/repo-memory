# Exploratory batch 01 (2026-10-04/05)

**Status: exploratory. Preserved as-is; do not regenerate its receipts.**

This was the first measured worker batch (3 conditions x 3 trials) for the
retry/idempotency coding experiment (#5). Its scores reproduced (repo-only
2/3, generic-retrieval 3/3, repo-memory 3/3), but PR #22 review found five
delivery/validation flaws, so this batch is kept as exploratory evidence
only and is superseded by the fresh batch collected under the fixed
protocol:

1. Receipt failures could still count as passing runs (now: a failed
   receipt forces the run to fail).
2. The memory arm did not receive the shared ordinary documents
   (now: both retrieval arms receive `corpus/retry-policy.md` and
   `corpus/idempotency-guide.md`).
3. Restricted incident rationale (INC-412) reached memory workers via the
   assertion rationale field (now: rationale withheld in all arms).
4. Receipts could be silently overwritten and execution metadata was not
   validated (now: `ReceiptConflictError` on conflicting re-issue;
   model/protocol/brief/timestamp validated).
5. A malformed job could abort the whole scoring batch (now: recorded as
   a failed run, batch continues).

Contents:

- `worker-jobs/` -- the nine job files as delivered (note: memory-arm jobs
  lack the corpus documents and carry the incident rationale).
- `worker-responses/` -- raw worker responses, extracted worker.py files,
  and the original execution-time receipts.
- `worker-worker-20261005-012847.json` -- the mechanical scoring report.

Recorded 2026-10-05.
