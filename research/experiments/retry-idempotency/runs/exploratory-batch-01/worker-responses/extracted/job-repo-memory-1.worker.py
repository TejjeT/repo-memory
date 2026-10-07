"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the retry/idempotency coding experiment.
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: add retry handling for transient settlement submission failures in
``settle_batch``.
"""
from gateway import GatewayClient, TransientError

# Gateway/client retry layer. Per EA-006, retry exists at exactly one layer
# (the worker): the client's built-in retry loop stays disabled.
GATEWAY_MAX_RETRIES = 0

# Worker-level retry bound for transient settlement submission failures.
WORKER_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch, retrying transient gateway failures.

    The same idempotency key is reused across every attempt (EA-002), so a
    retry after a lost response deduplicates instead of settling twice.
    Permanent errors are not retried.
    """
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            if attempts >= WORKER_MAX_RETRIES:
                raise
            attempts += 1
