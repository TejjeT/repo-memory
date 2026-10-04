"""Reference (valid) implementation: worker-layer retry, stable key.

Retry lives only in settle_batch. The idempotency key is generated once
per batch by the caller and reused unchanged across every retry attempt.
The gateway/client retry layer stays disabled (EA-006: exactly one
orchestration layer).
"""
from gateway import GatewayClient, TransientError

GATEWAY_MAX_RETRIES = 0

# Worker-layer retry budget.
WORKER_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            attempts += 1
            if attempts > WORKER_MAX_RETRIES:
                raise
            # Same idempotency_key is resubmitted: the key survives the
            # retry boundary (EA-002).
