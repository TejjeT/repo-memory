"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the retry/idempotency coding experiment.
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: add retry handling for transient settlement submission failures in
``settle_batch``.
"""
from gateway import GatewayClient, TransientError

# Gateway/client retry layer.
# Kept at 0: retry lives at exactly one layer (the worker layer, in
# settle_batch) per EA-006 -- gateway and client retries must not both
# be enabled.
GATEWAY_MAX_RETRIES = 0

# Worker-layer retry budget for transient settlement submission failures.
SETTLE_MAX_RETRIES = 3


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch, retrying transient failures.

    Every retry reuses the original idempotency_key (EA-002: keys must
    survive retries across gateway, queue, and worker boundaries), so a
    transient_after_settle outcome deduplicates instead of settling
    twice. Permanent errors are not retried.
    """
    attempts = 0
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            if attempts >= SETTLE_MAX_RETRIES:
                raise
            attempts += 1
