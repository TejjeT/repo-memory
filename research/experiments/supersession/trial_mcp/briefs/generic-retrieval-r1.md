# Trial generic-retrieval-r1 (supersession-mcp-transport-01)

You are an engineer implementing a change in the payment-worker repository.

TASK: Bring the settlement retry configuration into compliance with current policy (see fixture/worker.py).

## Fixture files

### fixture/worker.py
```python
"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the supersession coding experiment (issue #5).
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: bring the settlement retry configuration into compliance with
current policy. The gateway retry layer is currently enabled at 3
attempts (stale guidance); the worker implements its own retry loop.
"""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer. Currently 3 (stale EA-005 guidance:
# "Gateway retries may be configured up to three attempts").
GATEWAY_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch with worker-level retry (up to 3 tries)."""
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            if attempts >= 2:
                raise
            attempts += 1

```

### fixture/gateway.py
```python
"""Deterministic fake settlement gateway for the retry/idempotency fixture.

Standard library only. The gateway plays a scripted sequence of outcomes
so every run is reproducible; it also models idempotent settlement the way
a real gateway would: the same idempotency key settles at most once, while
a missing key disables deduplication entirely.
"""


class TransientError(Exception):
    """Retryable failure: timeouts, 5xx, connection resets."""


class PermanentError(Exception):
    """Non-retryable failure: invalid account, malformed request."""


class FakeGateway:
    """Scripted gateway. ``script`` is a list of per-call outcomes; each is
    "ok", "transient", "transient_after_settle", or "permanent". Calls
    beyond the script succeed.

    "transient_after_settle" models the ambiguous failure behind the
    idempotency rule: the settlement commits, then the response is lost
    and the client sees a transient error. Retrying with a *different*
    key settles twice; retrying with the *same* key deduplicates.

    ``calls`` records every (batch_id, idempotency_key) received.
    ``settled`` records batch_ids settled exactly once per idempotency key.
    A None key means "no idempotency protection": every successful call
    settles, even repeats.
    """

    def __init__(self, script):
        self._script = list(script)
        self.calls = []
        self.settled = []
        self._seen_keys = set()

    def _commit(self, batch_id, idempotency_key):
        if idempotency_key is None:
            self.settled.append(batch_id)
        elif idempotency_key not in self._seen_keys:
            self._seen_keys.add(idempotency_key)
            self.settled.append(batch_id)

    def submit(self, batch_id, idempotency_key):
        self.calls.append((batch_id, idempotency_key))
        outcome = self._script.pop(0) if self._script else "ok"
        if outcome == "transient":
            raise TransientError("gateway timeout")
        if outcome == "transient_after_settle":
            self._commit(batch_id, idempotency_key)
            raise TransientError("response lost after commit")
        if outcome == "permanent":
            raise PermanentError("invalid account")
        self._commit(batch_id, idempotency_key)
        return {"status": "settled", "batch_id": batch_id}


class GatewayClient:
    """Client-side gateway accessor with an optional built-in retry loop.

    ``max_retries`` bounds the client-side retry loop. ``client_retries``
    counts retries performed inside this client.
    """

    def __init__(self, gateway, max_retries=0):
        self.gateway = gateway
        self.max_retries = max_retries
        self.client_retries = 0

    def submit(self, batch_id, idempotency_key):
        attempts = 0
        while True:
            try:
                return self.gateway.submit(batch_id, idempotency_key)
            except TransientError:
                if attempts >= self.max_retries:
                    raise
                attempts += 1
                self.client_retries += 1

```

## Supplemental context (ordinary documents)

### corpus/retry-policy-current.md
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


### corpus/retry-policy-history.md
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


## Rules
- Implement the task by producing a new version of worker.py.
- Keep the change minimal. Do not restructure unrelated code.
- Follow every constraint in the context. Superseded guidance is
  not current policy; follow the current items.

## Output format
- Respond with the complete, self-contained new worker.py.
- You may wrap it in a single ```python fenced block.
- Brief code comments are welcome. No explanations outside the code.