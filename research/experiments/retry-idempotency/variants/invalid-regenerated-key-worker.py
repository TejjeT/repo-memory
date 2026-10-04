"""KNOWN-INVALID: regenerated idempotency key.

Looks locally reasonable (retry with "fresh" metadata), but each attempt
uses a new key, so the gateway treats every retry as a new settlement.
Violates EA-002. Expected: R1 and R2 fail.
"""
import uuid

from gateway import GatewayClient, TransientError

GATEWAY_MAX_RETRIES = 0

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
            # BUG: fresh key per attempt -- the gateway cannot deduplicate.
            idempotency_key = f"{batch_id}-{uuid.uuid4()}"
