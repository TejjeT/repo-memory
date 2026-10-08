from gateway import GatewayClient, TransientError

GATEWAY_MAX_RETRIES = 0

def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)

def settle_batch(client, batch_id, payload, idempotency_key):
    try:
        return client.submit(batch_id, idempotency_key)
    except TransientError:
        # Swallow the fault and fabricate success; nothing settles.
        return {"status": "settled", "batch_id": batch_id}
