# Settlement retry policy (CURRENT)

**Status: current as of 2026-06-12. Supersedes the August 2025 guidance.**

## One retry layer

Settlement submission retries must exist at **exactly one orchestration
layer**. The worker owns retry for settlement submission; the
gateway/client retry layer must stay disabled (`max_retries = 0`).

Rationale: two active retry layers multiply attempts against the
settlement gateway. Under load this amplifies duplicate-submission risk
and makes backoff unpredictable, because neither layer can see the
other's attempts.

## What this means in code

- Keep the worker-level retry loop.
- Set gateway/client `max_retries` to 0.
- A gateway `max_retries` of 3 was permitted under the old guidance; it
  is not permitted now.

## Failure handling

- Transient failures (timeouts, 5xx, connection resets): retry at the
  worker layer with the same request.
- Permanent failures (invalid account, malformed request): do not retry;
  surface the error.

## History

The August 2025 guidance allowed gateway retries up to three attempts.
That guidance was superseded on 2026-06-12 after it caused retry-layer
conflicts in production. Do not follow the old document.
