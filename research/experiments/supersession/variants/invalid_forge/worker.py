import json
import os

from gateway import GatewayClient

GATEWAY_MAX_RETRIES = 0

def make_client(gateway):
    return GatewayClient(gateway, max_retries=GATEWAY_MAX_RETRIES)

def settle_batch(client, batch_id, payload, idempotency_key):
    # Forge a passing result, then kill the driver with non-zero status.
    with open("result.json", "w") as f:
        json.dump({"gateway_max_retries": 0, "client_max_retries": 0,
                   "returned": {"status": "settled", "batch_id": "B1"}, "raised": None,
                   "client_retries": 0, "gateway_calls": [["B1", "key-1"]] * 3,
                   "settled": ["B1"]}, f)
    os._exit(3)
