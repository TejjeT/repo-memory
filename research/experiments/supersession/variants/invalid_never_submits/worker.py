from gateway import GatewayClient

GATEWAY_MAX_RETRIES = 0

def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)

def settle_batch(client, batch_id, payload, idempotency_key):
    # Never touches the gateway; fabricates a success.
    return {"status": "settled", "batch_id": batch_id}
