# Engineering Assertion Schema Rationale

The v0 schema is intentionally small. A field is required only when the policy engine or governance model cannot safely operate without it.

## Required fields

### `id`

A stable identity is required for:

- supersession
- overrides
- conflicts
- audit history
- references from external systems

### `type`

Type communicates the engineering meaning of the assertion and allows future policy to distinguish, for example, an approved exception from a convention.

### `content`

The durable engineering statement itself.

### `scope`

Memory without explicit applicability is dangerous. Scope is required so retrieval can be constrained deterministically before semantic ranking.

### `status`

Lifecycle state determines whether an assertion is eligible for normal retrieval.

### `importance`

Importance is required for deterministic ordering and later context-budget decisions. It represents consequence if missed, not confidence.

### `provenance`

At least one source is required. An engineering assertion without evidence becomes an unattributed organizational rule and is difficult to validate, govern, or retire.

Human assertions are allowed as provenance when no machine-addressable artifact exists.

### `created_at`

Required for auditability and lifecycle reasoning.

## Optional fields

### `rationale`

Useful when the assertion alone does not explain the engineering reason.

### `applies_to`

Used when the hierarchical scope alone cannot express legitimate cross-repository applicability.

### `confidence`

Useful for inferred or agent-proposed knowledge. Approved human-authored policies may not need a probabilistic value.

### `owner`

Recommended for important organizational assertions, but not all early examples have a stable owning team.

### `effective_from`, `review_after`, `expires_at`

Temporal fields are optional because some assertions are immediately effective and have no predetermined review or expiry date.

### `overrides`

Used by an approved exception to explicitly name assertions it replaces within its applicable scope.

### `supersedes` / `superseded_by`

Preserve historical relationships when guidance changes.

### `conflicts_with`

Allows unresolved contradictions to be represented without asking an LLM to choose a winner.

### `authorization`

The core model supports authorization metadata, but the actual authorization decision belongs to the deployment/integration layer. Omitting this field does not imply public access.

### creator / approver metadata

`created_by`, `approved_by`, and `approved_at` improve auditability but are optional in v0 so imported historical assertions can still conform.

## Design rule

A field should enter the required set only when its absence would make deterministic retrieval, governance, or audit behavior unsafe or undefined.
