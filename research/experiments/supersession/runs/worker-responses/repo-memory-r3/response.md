```python
"""Payment worker: settles batches via the gateway client.

Task: bring the settlement retry configuration into compliance with
current policy (EA-006): retry lives at exactly one orchestration layer,
owned by the worker; the gateway/client retry layer stays disabled.
"""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer disabled per current policy (EA-006).
# The August 2025 guidance allowing 3 attempts (EA-005) was superseded
# on 2026-06-12 and must not be followed.
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
