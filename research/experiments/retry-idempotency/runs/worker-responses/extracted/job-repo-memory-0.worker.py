"""Payment worker: settles batches via the gateway client.

FROZEN STARTING POINT for the retry/idempotency coding experiment.
Do not modify in place -- the evaluator copies this file into isolated
directories and applies one candidate variant per run.

Task: add retry handling for transient settlement submission failures in
``settle_batch``.
"""
from gateway import GatewayClient, TransientError

# Gateway/client retry layer.
# Stays at 0: the worker owns the single retry layer for settlement
# submission (corpus/retry-policy.md, EA-006). Enabling client retries
# alongside the worker loop would be a policy violation.
GATEWAY_MAX_RETRIES = 0


def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)


def settle_batch(client, batch_id, payload, idempotency_key):
    """Submit one settlement batch, retrying transient failures.

    The caller-provided idempotency key is reused unchanged on every
    attempt so retries deduplicate at the gateway instead of settling
    twice (corpus/idempotency-guide.md, EA-002). Permanent failures are
    not retried; they propagate to the caller.
    """
    while True:
        try:
            return client.submit(batch_id, idempotency_key)
        except TransientError:
            pass
