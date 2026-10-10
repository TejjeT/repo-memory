```python
"""Payment worker: settles batches via the gateway client.

Task: bring the settlement retry configuration into compliance with
current policy. Per the current retry policy (2026-06-12), settlement
submission retries must exist at exactly one orchestration layer, owned
by the worker; the gateway/client retry layer stays disabled. The
August 2025 guidance (gateway retries up to three attempts) is
superseded and is not followed.
"""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer: disabled (0) per current policy. Retry
# ownership belongs to the worker loop below.
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
