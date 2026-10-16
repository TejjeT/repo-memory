# Settlement retry decisions — permitted ordinary-source corpus

Synthetic engineering scenario, not a claim about a real organization.
The complete corpus is delivered to BOTH retrieval arms. These documents
carry all policy facts available through structured assertions; the
generic arm is an oracle-document baseline, not a tuned search algorithm.

## doc://payments/retry-2025 — historical, superseded 2026-06-12

EA-ROUTE-OLD applied throughout Acme / Payments / Settlement Platform.
Gateway and worker could each attempt settlement three times. It was
superseded by EA-ROUTE-CURRENT and is not current guidance.

## doc://payments/retry-2026 — effective 2026-06-12

EA-ROUTE-CURRENT supersedes EA-ROUTE-OLD. Exactly one layer owns retries.
Within Acme / Payments / Settlement Platform, the default is three total
worker attempts and one total gateway attempt. Preserve batch identity and
idempotency keys across attempts. Retry transient failures only; permanent
failures stop immediately. Return the actual successful gateway response.

This default applies to payment-worker, clearing-adapter and
reconciliation-worker, subject to the approved exception below.

## doc://payments/clearing-exception — approved 2026-07-01

EA-ROUTE-EXCEPTION explicitly overrides EA-ROUTE-CURRENT for
clearing-adapter only, through 2027-01-01 (exclusive). Its certified
connector owns retry orchestration: three total gateway attempts, one total
worker attempt. Identity, error classification and success requirements
are the same as the default. It does not apply to either other repository.

## doc://analytics/retry — current, different system

EA-ROUTE-ANALYTICS applies to Acme / Analytics / Report Platform only:
one total attempt at each layer. It has no applicability to settlement.

## Source equivalence

| Document | Assertion | Facts |
|---|---|---|
| retry-2025 | EA-ROUTE-OLD | Historical dual-layer rule and supersession |
| retry-2026 | EA-ROUTE-CURRENT | Scope, dates, attempts, identity/error/success rules |
| clearing-exception | EA-ROUTE-EXCEPTION | Explicit override, repository and expiry |
| analytics/retry | EA-ROUTE-ANALYTICS | Different-system rule, no settlement applicability |

Restricted incident background is withheld in all arms. Only the approved
conclusions above are readable. The repository-only arm receives fixture
files and task text, with no policy documents or assertion/evaluator code.
