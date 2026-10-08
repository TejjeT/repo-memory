```python
"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the supersession coding experiment (issue #5).
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: bring the settlement retry configuration into compliance with
current policy. The worker implements its own retry loop; the gateway
retry layer must stay disabled per current policy.
"""

from gateway import GatewayClient, TransientError

# Gateway/client retry layer. Disabled per current policy (EA-006):
# retry exists at exactly one orchestration layer, worker-owned, so the
# gateway layer stays off. The old "up to three attempts" guidance
# (EA-005) was superseded on 2026-06-12 and must not be followed.
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
