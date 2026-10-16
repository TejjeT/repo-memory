"""Retry configuration consumed by the settlement engine."""

from typing import NamedTuple


class RetryPlan(NamedTuple):
    gateway_attempts: int
    worker_attempts: int


def retry_plan(repository):
    return RetryPlan(gateway_attempts=1, worker_attempts=1)
