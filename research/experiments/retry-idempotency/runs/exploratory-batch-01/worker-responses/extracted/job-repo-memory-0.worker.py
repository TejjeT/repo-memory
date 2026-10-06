"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the retry/idempotency coding experiment.
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: add retry handling for transient settlement submission failures in
``settle_batch``.
"""
from gateway import GatewayClient, TransientError

# Gateway/client retry layer.
# Kept disabled: retry lives in the worker layer (settle_batch) so that
# retries exist at exactly one orchestration layer (EA-006).
GATEWAY_MAX_RETRIES = 0

# Worker retry layer for transient settlement submission failures.
WORKER_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch, retrying transient gateway failures.

    The same idempotency key is reused across every retry so the gateway
    deduplicates the retried submissions (EA-002). Non-transient failures
    (e.g. PermanentError) propagate immediately without retry.
    """
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            if attempts >= WORKER_MAX_RETRIES:
                raise
            attempts += 1
