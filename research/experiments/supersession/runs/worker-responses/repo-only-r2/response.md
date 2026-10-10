```python
"""Payment worker: settles batches via the gateway client.

Task: bring the settlement retry configuration into compliance with
current policy. Retry exists at exactly one orchestration layer -- the
worker owns it -- so the gateway/client retry layer stays disabled.
"""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer. Disabled (0): the worker implements its own
# retry loop, and two active retry layers would multiply attempts against
# the settlement gateway with unpredictable backoff behavior.
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
