"""KNOWN-INVALID: duplicate retry layer.

Adds a worker retry loop AND enables the gateway/client retry layer.
Both layers retry the same transient fault, multiplying attempts.
Violates EA-006 (exactly one orchestration layer). Expected: R5 fails.
"""
from gateway import GatewayClient, TransientError

# BUG: gateway retry layer enabled while the worker also retries.
GATEWAY_MAX_RETRIES = 3

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
