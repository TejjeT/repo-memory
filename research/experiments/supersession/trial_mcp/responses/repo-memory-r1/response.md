```python
"""Payment worker: settles batches via the gateway client."""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer. Disabled per EA-006 (supersedes EA-005):
# retry must exist at exactly one orchestration layer, and the worker
# implements its own retry loop below.
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
