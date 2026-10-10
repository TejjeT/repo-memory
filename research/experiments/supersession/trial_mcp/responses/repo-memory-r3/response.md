```python
"""Payment worker: settles batches via the gateway client.

Retry policy per EA-006 (supersedes stale EA-005 guidance):
retry must exist at exactly one orchestration layer, so the
gateway retry layer is disabled and the worker owns retries.
"""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer. Disabled (0) per current policy EA-006:
# retry must exist at exactly one orchestration layer. The worker
# implements its own retry loop below, so gateway retries stay off.
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
