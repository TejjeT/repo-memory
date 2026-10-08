import os

from gateway import GatewayClient, TransientError

GATEWAY_MAX_RETRIES = 0

def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)

def settle_batch(client, batch_id, payload, idempotency_key):
    try:
        return client.submit(batch_id, idempotency_key)
    except TransientError:
        os._exit(1)  # hard crash: driver never writes result.json
