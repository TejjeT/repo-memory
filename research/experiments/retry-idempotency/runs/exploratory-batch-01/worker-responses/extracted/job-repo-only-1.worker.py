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

# Retry layer for settle_batch: transient submission failures only.
SETTLE_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch, retrying transient gateway failures.

    The same idempotency_key is reused on every attempt so an ambiguous
    failure (settlement committed, response lost) deduplicates on the
    gateway instead of settling twice. Permanent errors propagate without
    retry.
    """
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            if attempts >= SETTLE_MAX_RETRIES:
                raise
            attempts += 1
