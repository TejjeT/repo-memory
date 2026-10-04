"""KNOWN-INVALID: unsafe repeated submission (no idempotency key).

Retries without any idempotency key, so every attempt settles as a new
payment. Violates EA-002. Expected: R1 and R2 fail.
"""
from gateway import GatewayClient, TransientError

GATEWAY_MAX_RETRIES = 0

WORKER_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    attempts = 0
    while True:
        try:
            # BUG: drops the key -- no deduplication across attempts.
            return client.submit(batch_id, None)
        except TransientError:
            attempts += 1
            if attempts > WORKER_MAX_RETRIES:
                raise
