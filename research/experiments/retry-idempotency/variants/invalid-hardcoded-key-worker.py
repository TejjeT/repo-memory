"""Counterexample: ignores the caller-provided idempotency key.

The worker submits every batch under the literal key "key-1". Single-batch
scenarios cannot tell -- but two distinct batches on one gateway collide:
the second batch reuses the first key and never settles. Must fail R1.
"""
from gateway import GatewayClient, TransientError

GATEWAY_MAX_RETRIES = 0


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    for _ in range(3):
        try:
            return client.submit(batch_id, "key-1")
        except TransientError:
            continue
    raise TransientError("exhausted")
