# Idempotency guide for settlement submissions

## Keys must survive retry boundaries

Every settlement submission carries an idempotency key. Generate the key
**once per settlement batch** and reuse the identical key on every retry
attempt, across gateway, queue, and worker retry boundaries.

A regenerated key is a new settlement as far as the gateway is concerned:
the same batch submitted twice under two different keys settles twice.

## Rules

- One batch, one key. The key is created before the first submission
  attempt and never regenerated for that batch.
- Every retry attempt resubmits with the original key.
- A missing key disables deduplication: without a key, repeated
  submissions settle repeatedly.

## Scope

Applies to payment-api, settlement-engine, and payment-worker --
anywhere a settlement submission can be retried.
