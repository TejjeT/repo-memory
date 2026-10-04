"""Counterexample: raises even when the submission succeeds.

After a successful submit the worker raises PermanentError. A clean run
then reports returned=None and raised=PermanentError. Must fail R3 (and R2).
"""
from gateway import GatewayClient, PermanentError, TransientError

GATEWAY_MAX_RETRIES = 0


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    for _ in range(3):
        try:
            client.submit(batch_id, idempotency_key)
        except TransientError:
            continue
        raise PermanentError("invalid account")
    raise TransientError("exhausted")
