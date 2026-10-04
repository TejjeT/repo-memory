# Settlement retry policy

## One retry layer

Settlement submission retries must exist at **exactly one orchestration
layer**. If the worker (client) implements retry, gateway/client-library
retries must stay disabled, and vice versa.

Rationale: two active retry layers multiply attempts against the
settlement gateway. Under load this amplifies duplicate-submission risk
and makes backoff behavior unpredictable, because neither layer can see
the other's attempts.

## What this means in code

- Pick the worker as the retry owner for settlement submission.
- Keep gateway/client `max_retries` at 0 when the worker retries.
- A retry loop in the worker plus enabled client retries is a policy
  violation, even if no fault occurs in a given run.

## Failure handling

- Transient failures (timeouts, 5xx, connection resets): retry with the
  same request.
- Permanent failures (invalid account, malformed request): do not retry;
  surface the error.
