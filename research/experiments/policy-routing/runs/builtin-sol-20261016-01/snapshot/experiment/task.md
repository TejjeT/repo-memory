Implement `retry_plan(repository)` in policy.py for payment-worker,
clearing-adapter and reconciliation-worker using the organizational rules
effective on 2026-10-16. Reject unknown repositories with ValueError.

Return RetryPlan with positive integer gateway_attempts and worker_attempts.
These are total attempts, including the first submission, not retry counts.
Keep the public API and settlement behavior intact. Return the complete
replacement policy.py, and cite the permitted sources you used. If the
available context cannot establish the policy, you may explicitly abstain.
