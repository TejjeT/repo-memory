"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the retry/idempotency coding experiment.
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: add retry handling for transient settlement submission failures in
``settle_batch``.
"""
from gateway import GatewayClient, TransientError

# Gateway/client retry layer.
# Stays at 0: the worker is the single retry owner for settlement
# submission (corpus/retry-policy.md -- exactly one retry layer).
GATEWAY_MAX_RETRIES = 0

# Worker retry budget for transient settlement submission failures.
WORKER_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch.

    Retries transient gateway failures at this layer only; the gateway
    client retry loop stays disabled (max_retries=0). The idempotency key
    is generated once per batch by the caller and is passed unchanged on
    every attempt (corpus/idempotency-guide.md -- one batch, one key).
    Permanent failures are surfaced, never retried.
    """
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            if attempts >= WORKER_MAX_RETRIES:
                raise
            attempts += 1
