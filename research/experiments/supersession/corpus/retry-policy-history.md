# Settlement retry policy (HISTORICAL)

**Status: SUPERSEDED on 2026-06-12. Do not follow; retained for history.**

## Old guidance (2025-08-01 to 2026-06-12)

Gateway retries could be configured up to three attempts. The worker
could also retry; the interaction between layers was not constrained.

## Why it was replaced

The unconstrained two-layer setup caused retry amplification against
the settlement gateway. The June 2026 policy requires exactly one
retry layer (worker-owned, gateway disabled).

## Current rule

See `retry-policy-current.md`. Gateway `max_retries` must be 0 when the
worker retries.
