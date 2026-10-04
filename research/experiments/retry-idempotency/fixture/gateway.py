"""Deterministic fake settlement gateway for the retry/idempotency fixture.

Standard library only. The gateway plays a scripted sequence of outcomes
so every run is reproducible; it also models idempotent settlement the way
a real gateway would: the same idempotency key settles at most once, while
a missing key disables deduplication entirely.
"""


class TransientError(Exception):
    """Retryable failure: timeouts, 5xx, connection resets."""


class PermanentError(Exception):
    """Non-retryable failure: invalid account, malformed request."""


class FakeGateway:
    """Scripted gateway. ``script`` is a list of per-call outcomes; each is
    "ok", "transient", "transient_after_settle", or "permanent". Calls
    beyond the script succeed.

    "transient_after_settle" models the ambiguous failure behind the
    idempotency rule: the settlement commits, then the response is lost
    and the client sees a transient error. Retrying with a *different*
    key settles twice; retrying with the *same* key deduplicates.

    ``calls`` records every (batch_id, idempotency_key) received.
    ``settled`` records batch_ids settled exactly once per idempotency key.
    A None key means "no idempotency protection": every successful call
    settles, even repeats.
    """

    def __init__(self, script):
        self._script = list(script)
        self.calls = []
        self.settled = []
        self._seen_keys = set()

    def _commit(self, batch_id, idempotency_key):
        if idempotency_key is None:
            self.settled.append(batch_id)
        elif idempotency_key not in self._seen_keys:
            self._seen_keys.add(idempotency_key)
            self.settled.append(batch_id)

    def submit(self, batch_id, idempotency_key):
        self.calls.append((batch_id, idempotency_key))
        outcome = self._script.pop(0) if self._script else "ok"
        if outcome == "transient":
            raise TransientError("gateway timeout")
        if outcome == "transient_after_settle":
            self._commit(batch_id, idempotency_key)
            raise TransientError("response lost after commit")
        if outcome == "permanent":
            raise PermanentError("invalid account")
        self._commit(batch_id, idempotency_key)
        return {"status": "settled", "batch_id": batch_id}


class GatewayClient:
    """Client-side gateway accessor with an optional built-in retry loop.

    ``max_retries`` is the client/gateway retry layer. The organization
    rule (EA-006) is that retry must exist at exactly one orchestration
    layer: when the worker implements its own retry, this must stay 0.
    ``client_retries`` counts retries performed inside this client, so the
    evaluator can detect a second retry layer behaviorally.
    """

    def __init__(self, gateway, max_retries=0):
        self.gateway = gateway
        self.max_retries = max_retries
        self.client_retries = 0

    def submit(self, batch_id, idempotency_key):
        attempts = 0
        while True:
            try:
                return self.gateway.submit(batch_id, idempotency_key)
            except TransientError:
                if attempts >= self.max_retries:
                    raise
                attempts += 1
                self.client_retries += 1
