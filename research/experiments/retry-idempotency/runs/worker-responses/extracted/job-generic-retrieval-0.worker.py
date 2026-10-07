"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the retry/idempotency coding experiment.
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: add retry handling for transient settlement submission failures in
``settle_batch``.
"""
from gateway import GatewayClient, TransientError

# Gateway/client retry layer. The worker owns retry for settlement
# submission, so the client layer stays disabled: retry must exist at
# exactly one orchestration layer.
GATEWAY_MAX_RETRIES = 0

# Worker-side retry budget for transient submission failures.
WORKER_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch, retrying transient gateway failures.

    The caller-provided idempotency key is reused unchanged on every
    attempt, so a retried submission deduplicates at the gateway instead
    of settling twice. Permanent failures are not retried and propagate
    to the caller.
    """
    retries = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            if retries >= WORKER_MAX_RETRIES:
                raise
            retries += 1
