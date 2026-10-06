"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the retry/idempotency coding experiment.
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: add retry handling for transient settlement submission failures in
``settle_batch``.
"""
from gateway import GatewayClient, TransientError

# Gateway/client retry layer: stays disabled. The worker owns the single
# retry layer for settlement submission.
GATEWAY_MAX_RETRIES = 0

# Worker-owned retry bound for transient settlement failures.
WORKER_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch, retrying transient failures.

    The worker owns the single retry layer: transient failures are retried
    here, resubmitting with the same idempotency key on every attempt (one
    batch, one key -- never regenerated). Permanent failures are not
    retried; they propagate to the caller.
    """
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            attempts += 1
            if attempts > WORKER_MAX_RETRIES:
                raise
