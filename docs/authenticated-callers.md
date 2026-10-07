# Authenticated Callers and the External Provider Boundary

Issue #20. This document names the trusted boundaries for caller-facing
deployments (remote API, MCP server) and the assumptions a deployment must
satisfy. It complements the [retrieval contract](retrieval-contract.md),
which defines the pipeline; this defines who is trusted at each edge.

## The problem

`Caller` (identity + granted source URI prefixes) and
`ContextAssembler.for_caller` give deterministic policy wiring, but `Caller`
is a trusted core input: anything that constructs one chooses its own
grants. Likewise, `EvidenceProvider.collect` receives unredacted assertion
provenance, which is only safe for trusted in-process providers. Neither is
a deployed identity or an external-provider security boundary.

## Trusted vs untrusted

| Component | Trust status | Rule |
|---|---|---|
| `VerifiedSession` | Trusted | Produced only by the deployment's identity layer (session store, OIDC, API-key lookup). Never constructed from client input. |
| `CallerDirectory` | Trusted | Server-side subject → grants mapping (group membership, repo permissions). The only source of permissions. |
| `Caller` returned by `authenticate()` | Trusted | Carries directory-derived grants. Client claims are validated, never applied. |
| Client-supplied caller id / grants / scope | Untrusted | Validated against the verified identity; mismatches and widening attempts raise `AuthorizationError`. |
| In-process `EvidenceProvider` | Trusted | Receives unredacted candidates, as documented in `context.py`. |
| External/untrusted provider | Untrusted | Receives only the redacted candidate view. Redaction is applied by the assembler with the request caller's own hook -- a provider object can never carry one caller's permissions into another caller's request. |
| Provider output | Untrusted | Cannot expand the authorized set: the assembler strips out-of-scope links, drops orphans, and enforces the evidence hook. |
| Assertion `rationale` | Caller-safe | Withheld whenever any provenance entry is redacted for the caller -- free-text rationale may discuss restricted sources. The approved conclusion (`content`) stays readable by design. |

## The authenticated path

```
client request ──► deployment verifies credentials ──► VerifiedSession
                                                              │
client claims (id/grants) ──► authenticate() validates ──► Caller (server grants)
                                                              │
                                              ┌───────────────┴───────────────┐
                                              │ ContextAssembler.for_caller   │
                                              │ (assertion/evidence/         │
                                              │  provenance hooks, one id)   │
                                              └───────────────┬───────────────┘
                                                              │
                                    external_providers ──► redacted view ──► record ──► collect
                                    (assembler's own hook; per-request binding)
```

Entry points (`src/repo_memory/auth.py`):

- `resolve_caller(session, directory)` — `None`/empty/unknown sessions raise
  `AuthenticationError`. Fail closed; unknown subjects do not leak existence.
- `authenticate(session, directory, *, claimed_caller_id, claimed_grants)` —
  resolves, then rejects id mismatches and grant-widening with
  `AuthorizationError`. Returns the server-derived caller.
- `assembler_for_session(...)` — one-call entry point: authenticate, then
  bind all hooks to that identity. No permissive fallback.

`assembler_for_session(...)` — one-call entry point: authenticate, then
bind all hooks to that identity. External providers are passed separately
and redacted inside `assemble` with the verified caller's own hook.

Redaction (`src/repo_memory/context.py`) is owned by the assembler, the only
component that knows the request's caller:

- `redacted_candidate_view()` builds the caller-safe view for external
  providers: unauthorized provenance entries are withheld and rationale is
  withheld with them.
- `redact_assertion()` applies the same rule to responses.
- `BoundaryTransport` records the exact outbound view for audit. The
  provenance hook is required when external providers are configured -- a
  missing hook fails fast rather than exposing unredacted data.

## What the demo shows

`examples/authenticated_callers_demo.py` runs two callers through the full
path with a recording transport:

- alice (`doc://`, `incident://`) sees both assertions with full provenance
- bob (`doc://`) sees only the public assertion; restricted provenance is
  redacted in his response *and* in what the external provider received
- the provider's hostile items (restricted source, restricted link) are
  dropped for the caller lacking authorization

## Deployment assumptions (not provided by core)

Core defines no identity provider, session store, or transport security.
A deployment must supply:

1. A credential-verification layer producing `VerifiedSession` (and
   protecting it in transit — TLS, signed session tokens, etc.).
2. A `CallerDirectory` backed by the real permission source of record.
3. An audit sink behind `BoundaryTransport`, if outbound views must be
   retained beyond tests.
4. Request authentication on every caller-facing entry point: the plain
   `ContextAssembler` constructor keeps permissive-when-omitted defaults for
   backward compatibility and is not a production identity boundary.

Non-goals (per #20): a new identity provider, vector database, persistence
engine, write/lifecycle APIs, or mandatory OpenViking semantic search. MCP
packaging is #4.
