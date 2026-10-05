"""Positive control: the reference worker with ordinary debug output.

A generated worker that prints to stdout must still score 5/5 -- candidate
output travels on a separate channel from the result protocol.
"""
from gateway import GatewayClient, TransientError

print("worker loaded")

GATEWAY_MAX_RETRIES = 0


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    for _ in range(3):
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            continue
    raise TransientError("exhausted")
