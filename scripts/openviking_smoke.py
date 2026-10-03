"""Optional smoke test against a running OpenViking server.

Usage:

    OPENVIKING_URL=http://localhost:1933 \
    OPENVIKING_API_KEY=... \
    python scripts/openviking_smoke.py

This script is intentionally excluded from CI because it requires a live server.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import openviking_sdk as ov

from repo_memory.adapters.openviking import OpenVikingAssertionStore
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext


def main() -> None:
    url = os.environ["OPENVIKING_URL"]
    api_key = os.environ["OPENVIKING_API_KEY"]

    client = ov.SyncHTTPClient(url=url, api_key=api_key)
    client.initialize()

    store = OpenVikingAssertionStore(client)
    assertion = EngineeringAssertion(
        id="EA-smoke",
        type="constraint",
        content="Smoke-test engineering assertion.",
        scope=Scope(
            organization="RepoMemorySmoke",
            domain="Testing",
            repository="smoke-repo",
        ),
        status="approved",
        importance="low",
        provenance=(Provenance(type="document", uri="test://openviking-smoke"),),
        created_at=datetime.now(UTC),
    )

    uri = store.put(assertion)
    result = store.resolve(
        ResolutionContext(scope=assertion.scope, when=datetime.now(UTC))
    )

    assert any(item.id == assertion.id for item in result.active)
    print(f"OpenViking smoke test passed: {uri}")


if __name__ == "__main__":
    main()
