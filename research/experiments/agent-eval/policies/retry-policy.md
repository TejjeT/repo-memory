# retry-policy.md

Current retry policy for payment-worker: exponential backoff with jitter, max 5 attempts. Supersedes the older fixed-delay policy.
