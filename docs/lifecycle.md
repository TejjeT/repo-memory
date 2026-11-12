# Governed Assertion Lifecycle

Issue #3. Implemented in `src/repo_memory/lifecycle.py`. Demo:
`python examples/lifecycle_demo.py`.

Read-time behavior (lifecycle filtering, supersession, overrides) is defined in
[applicability-and-precedence.md](applicability-and-precedence.md) and is
unchanged. This document covers **writes**: who may change an assertion's
state, under which rules, and what is recorded.

No LLM takes part in any decision here. Every rule is a table lookup or a
comparison.

## Transitions

```text
(new) ──propose──▶ proposed ──approve──▶ approved ──supersede──▶ superseded
                      │                     │
                      └──reject──▶ rejected └──expire──▶ expired

proposed | approved | rejected | superseded | expired ──archive──▶ archived
```

| Action | From | To | Role | Extra rules |
|---|---|---|---|---|
| `propose` | (does not exist) | `proposed` | proposer | At least one provenance source; organization scope set; must not arrive with `superseded_by`; every ID it references must be readable by the proposer. The status in the request is ignored and forced to `proposed`. |
| `approve` | `proposed` | `approved` | approver | The proposer may not approve their own proposal unless the deployment sets `allow_self_approval`. Every assertion named in `supersedes` must be `approved`, in the same organization, and is marked `superseded` in the same commit. |
| `reject` | `proposed` | `rejected` | approver | |
| `supersede` | `approved` | `superseded` | approver on both scopes | The successor must already be `approved` and in the same organization. Both records are linked in one commit. |
| `expire` | `approved` | `expired` | approver | |
| `archive` | any except `archived` | `archived` | approver | Terminal. |

Anything not in this table is refused. In particular `rejected`, `superseded`
and `expired` assertions cannot be re-approved; propose a new assertion.

Every action requires a non-empty reason.

## What a transition may change

Only `status` and the relationship links `supersedes` / `superseded_by`.
Content, scope, importance and provenance are never rewritten, so a
superseded or archived assertion still shows exactly what was once approved
and on what evidence. To change guidance, propose a successor.

## Authorization

1. **Identity** comes from `repo_memory.auth.authenticate`: a
   `VerifiedSession` produced by the deployment plus a server-side
   `CallerDirectory`. A missing session fails closed. Nothing in the request
   body selects the actor.
2. **Read access** uses the same rule as retrieval: the caller must be granted
   at least one of the assertion's provenance sources.
3. **Role** is decided by a `LifecycleAuthority`: may this subject act as
   `proposer` or `approver` on this scope? The reference
   `ScopeRoleAuthority` holds explicit (subject, role, scope) grants; a grant
   on a scope covers its descendants; an absent grant is a denial.

Error behavior is deliberate:

| Situation | Code |
|---|---|
| Unknown ID, or an ID the caller may not read | `not_found` (identical message, so existence is not revealed) |
| Readable, but the caller lacks the role | `forbidden` |
| Request breaks a rule above | `invalid` |
| Assertion is in a state that does not allow the action | `conflict` |
| The same decision is already recorded | `already_done` |
| Another writer changed the record first | `concurrent` |

A refused operation writes nothing.

## Governance history

Each transition appends one immutable `GovernanceEvent`:

- action, assertion ID, from and to status
- actor (verified subject), authentication method, timestamp
- reason
- **source revisions**: the URI and revision of every provenance entry at the
  moment of the decision, so the record shows what evidence state was approved
- related assertion IDs (for supersession)

`LifecycleService.history` returns a caller-safe view: source URIs the caller
may not access are replaced by `redacted`, and related IDs the caller may not
read are withheld.

## Storage contract

`LifecycleStore` is four methods: `load`, `commit`, `history`, `assertions`.
`commit` takes every write with the version the caller read (0 means "must
not exist") and applies all of them with their events, or none, raising
`ConcurrentModification` on any mismatch.

| Store | Where | Atomic commit | Notes |
|---|---|---|---|
| `InMemoryLifecycleStore` | core | Yes, within one process | Reference implementation |
| `OpenVikingLifecycleStore` | `adapters/openviking.py` | **No** | Assertion JSON stays where the existing adapter writes it; version and events live in a sidecar with the same ACL |

The OpenViking client protocol has no conditional write and no multi-resource
transaction. That store detects stale versions but cannot prevent two writers
racing between check and write, and a supersession is two writes. **Use a
single governing writer** until the backend provides a conditional write. It
has been tested against the in-repo fake client only, not a live server.

## Known limits and open questions

- **Hidden successor.** A caller who can read a superseded assertion but not
  its successor sees `status: superseded` with the successor ID withheld. They
  learn that a replacement exists but not what it says. The read-side form of
  this trade-off is tracked in #41 and #44.
- **Read-time gap closed for governed writes only.** Supersession through this
  service always updates both records, so the "left approved" predecessor seen
  in the delivery ablation cannot be created here. Assertions written directly
  to storage are not checked.
- **Roles are minimal.** Two roles, scope ancestry, no delegation, no quorum,
  no approval expiry.
- **No transport.** Nothing here is exposed over MCP. The MCP server stays
  read-only; governed MCP writes are a separate decision.
- **The dataclass model has no `created_by` / `approved_by`.** Attribution
  lives in the event log, not on the assertion.

## Relation to other work

[Mneme HQ](../research/open-source/mneme.md) implements governed writes for
single-repository decision records and records identity as unauthenticated
claims. What this slice adds is the part Mneme places outside its core:
verified identity, scope-based roles across an organization hierarchy, and
history that is redacted per caller.
