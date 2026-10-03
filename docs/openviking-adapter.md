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

1. traverse the organization subtree level by level with non-recursive `ls`
2. skip access-denied entries (and do not descend into denied directories)
3. read canonical assertion JSON
4. run repo-memory deterministic authorization/applicability/lifecycle rules
5. optionally add semantic ranking later within the safe set

Level-by-level traversal is deliberate: live-server verification (OpenViking
0.4.23) showed the server's recursive `ls` returns descendant directories
without their files, so the adapter does not rely on recursive listing
semantics.

This deliberately matches the retrieval contract:

> determine what may be considered before deciding what is most relevant.

## ACL behavior

The adapter accepts an `acl_resolver(assertion)` callback.

The deployment may map engineering scope/ownership to OpenViking ACLs without adding enterprise identity assumptions to the core package.

OpenViking's current ACL model supports resource-level ACLs and inherited permissions.

### Live ACL verification (2026-10-03, OpenViking 0.4.23, `api_key` mode)

Verified against a live server with ACL enforcement enabled (`PATCH
/api/v1/admin/accounts/{id}/settings` `{"acl": {"enabled": true}}`):

- A restricted directory (`acl_mode=restricted`, direct grant `user:alice=read`)
  denies `bob` on both `read` (`PermissionDeniedError`) and `ls` into the
  directory (`PermissionDeniedError`).
- The restricted directory **name** still appears in the parent's `ls`
  results; only its contents are protected. The adapter therefore cannot rely
  on listings to hide denied subtrees — it must handle the denial when
  descending.
- The unit tests originally simulated denial with entries marked
  `{"access": "denied"}`. The live server **raises** instead of marking, so
  `_walk_files` and the read path now catch authorization denials
  (`PermissionDeniedError` and equivalents, matched by class name so the
  adapter stays SDK-agnostic) and skip those entries without descending.
- End-to-end: `list_for_organization` as `bob` returns only the public
  assertion; as `alice` it returns both.
- Indexing lag caveat: `acl_set` on a freshly written directory fails with
  "ACL target has no context record; index it first" until the server's
  index catches up. ACL changes also take effect as index updates complete,
  so retrieval filtering is eventually consistent.

## What is tested

Unit tests cover:

- deterministic URI mapping
- JSON persistence
- retrieval tags
- ACL propagation
- policy resolution after loading OpenViking candidates
- skipping access-denied entries (both marked entries and raised denials)

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
