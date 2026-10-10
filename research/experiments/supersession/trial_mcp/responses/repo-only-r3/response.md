```python
"""Payment worker: settles batches via the gateway client.

Retry policy: the worker owns the single retry layer (up to 3 attempts in
settle_batch); the gateway/client retry layer must stay disabled. EA-005
("Gateway retries may be configured up to three attempts") is superseded
guidance and is not current policy.
"""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer. 0 (disabled): superseded EA-005 guidance
# allowed up to 3, but current policy keeps retries worker-owned only.
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
