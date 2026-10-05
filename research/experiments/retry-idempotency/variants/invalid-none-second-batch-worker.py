"""Counterexample: returns None for the second batch.

Both batches settle under the right caller keys, but the worker swallows
the second batch's settled response. Completion must be verified for every
batch in a scenario, not just the first. Must fail R1.
"""
from gateway import GatewayClient, TransientError

GATEWAY_MAX_RETRIES = 0


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    for _ in range(3):
        try:
            result = client.submit(batch_id, idempotency_key)
        except TransientError:
            continue
        if batch_id == "batch-B":
            return None
        return result
    raise TransientError("exhausted")
