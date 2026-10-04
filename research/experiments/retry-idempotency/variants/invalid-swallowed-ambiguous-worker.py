"""Counterexample: swallows the ambiguous failure.

On the response-lost TransientError the worker returns None instead of
retrying. The first attempt already committed, so the settlement count is
right -- but the caller never gets the settled response. Must fail R2.
"""
from gateway import GatewayClient, TransientError

GATEWAY_MAX_RETRIES = 0


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    for _ in range(3):
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError as e:
            if "response lost" in str(e):
                return None
    raise TransientError("exhausted")
