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

# Gateway/client retry layer disabled per current single-retry-layer policy:
# worker-level retry owns retries. Supersedes stale EA-005 guidance
# ("Gateway retries may be configured up to three attempts").
GATEWAY_MAX_RETRIES = 0


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
