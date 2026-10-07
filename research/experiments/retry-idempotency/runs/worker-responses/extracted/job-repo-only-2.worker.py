"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the retry/idempotency coding experiment.
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: add retry handling for transient settlement submission failures in
``settle_batch``.
"""
from gateway import GatewayClient, TransientError

# Gateway/client retry layer.
GATEWAY_MAX_RETRIES = 0

# Worker-owned retry layer: bounded retries for transient submission
# failures. The gateway/client layer stays disabled so retry exists at
# exactly one orchestration layer.
WORKER_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch, retrying transient gateway failures.

    The same idempotency key is reused on every attempt: if the gateway
    committed the settlement but the response was lost, retrying with the
    same key deduplicates instead of settling twice. Permanent failures
    are not retried and propagate to the caller.
    """
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            attempts += 1
            if attempts > WORKER_MAX_RETRIES:
                raise
