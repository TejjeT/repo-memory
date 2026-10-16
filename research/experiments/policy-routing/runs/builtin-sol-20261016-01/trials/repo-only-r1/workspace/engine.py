"""Settlement plumbing; retry ownership is supplied by policy.py."""

from gateway import GatewayClient, TransientError
from policy import retry_plan


def settle(gateway, repository, batch_id, idempotency_key):
    plan = retry_plan(repository)
    client = GatewayClient(gateway, max_retries=plan.gateway_attempts - 1)
    for attempt in range(plan.worker_attempts):
        try:
            return client.submit(batch_id, idempotency_key), client.client_retries
        except TransientError:
            if attempt + 1 == plan.worker_attempts:
                raise
