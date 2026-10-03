# OpenViking Adapter

The v0 OpenViking integration treats OpenViking as **storage, ACL, indexing, and context infrastructure**.

repo-memory remains responsible for engineering semantics.

## Boundary

```text
Engineering Assertion
        |
        v
repo-memory policy engine
        |
        v
OpenVikingAssertionStore
        |
        v
OpenViking shared resources
```

The core package does not import the OpenViking SDK.

Instead, the adapter accepts any client implementing the minimal methods:

- `write`
- `read`
- `ls`

The official OpenViking Python `SyncHTTPClient` exposes compatible operations.

Install the optional SDK dependency with:

```bash
pip install -e ".[openviking]"
```

## Storage layout

Assertions are stored as canonical JSON below:

```text
viking://resources/repo-memory/assertions/
  <organization>/
    <domain-or-_>/
      <system-or-_>/
        <repository-or-_>/
          <assertion-id>.json
```

Example:

```text
viking://resources/repo-memory/assertions/
  acme/
    payments/
      settlement-platform/
        _/
          ea-002.json
```

## Why shared resources, not OpenViking user memory

OpenViking documents resources as shared reference context and user memories as durable context learned for a user/peer.

Engineering Assertions are organizational artifacts, so the shared `resources` namespace is the more natural mapping.

## Write behavior

The adapter writes:

1. canonical assertion JSON
2. deterministic retrieval tags
3. optional OpenViking ACL supplied by the deployment

Example tags:

```text
assertion_id=EA-002
type=incident-derived-constraint
status=approved
importance=critical
organization=acme
domain=payments
system=settlement-platform
```

## Retrieval behavior

v0 does **not** use semantic search to determine the authoritative candidate set.

Instead:

1. enumerate readable assertion files under the organization root using recursive `ls`
2. skip access-denied entries
3. read canonical assertion JSON
4. run repo-memory deterministic authorization/applicability/lifecycle rules
5. optionally add semantic ranking later within the safe set

This deliberately matches the retrieval contract:

> determine what may be considered before deciding what is most relevant.

## ACL behavior

The adapter accepts an `acl_resolver(assertion)` callback.

The deployment may map engineering scope/ownership to OpenViking ACLs without adding enterprise identity assumptions to the core package.

OpenViking's current ACL model supports resource-level ACLs and inherited permissions.

## What is tested

Unit tests cover:

- deterministic URI mapping
- JSON persistence
- retrieval tags
- ACL propagation
- policy resolution after loading OpenViking candidates
- skipping access-denied entries

Tests use an in-memory compatible client so CI does not require an OpenViking server.

## What is not yet proven

A live-server smoke test is still required before calling the integration production-ready.

Run it against a reachable server with:

```bash
OPENVIKING_URL=http://localhost:1933 \\
OPENVIKING_API_KEY=... \\
python scripts/openviking_smoke.py
```

That test should verify:

- official `SyncHTTPClient` compatibility
- recursive `ls` response shape
- ACL-denied entry behavior
- read/write semantics
- semantic/vector refresh behavior
