```python
"""Payment worker: settles batches via the gateway client.

Task: bring the settlement retry configuration into compliance with
current policy. Per the current retry policy (2026-06-12, superseding the
August 2025 guidance), retries must exist at exactly one orchestration
layer: the worker owns retry for settlement submission, so the
gateway/client retry layer stays disabled (max_retries = 0).
"""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer. Disabled per current policy: the worker owns
# retry, and the old "up to three gateway attempts" guidance is superseded.
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
