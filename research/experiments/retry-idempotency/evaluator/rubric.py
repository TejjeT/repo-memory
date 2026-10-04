"""Mechanical evaluator for the retry/idempotency coding experiment.

No LLM policy decisions anywhere: each candidate variant is a ``worker.py``
replacement applied to an isolated copy of the frozen fixture, then
exercised against scripted gateway scenarios in a subprocess. Every check
is a deterministic predicate over recorded gateway calls.

Rubric (predeclared):
  R1 key_stable          -- the idempotency key is identical (and present)
                            across all submit attempts of one batch
  R2 no_duplicate        -- a transient failure settles the batch exactly once
  R3 transient_retried   -- transient faults are retried until success
  R4 permanent_stops     -- a permanent fault raises without retrying
  R5 single_retry_layer  -- the task assigns retry ownership to the worker
                            (settle_batch); the gateway/client layer must
                            stay disabled AND unexercised
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_DIR = HERE.parent / "fixture"

DRIVER = """\
import json, sys
from gateway import FakeGateway, TransientError, PermanentError
import worker

scenario = json.loads(sys.argv[1])
gateway = FakeGateway(scenario["script"])
client = worker.make_client(gateway)
result = {
    "calls": None,
    "settled": None,
    "client_max_retries": client.max_retries,
    "client_retries": None,
    "returned": None,
    "raised": None,
}
try:
    out = worker.settle_batch(client, "batch-1", {"amount": 100}, "key-1")
    result["returned"] = out
except Exception as e:  # noqa: BLE001 -- the fixture must surface faults
    result["raised"] = type(e).__name__
result["calls"] = [list(c) for c in gateway.calls]
result["settled"] = gateway.settled
result["client_retries"] = client.client_retries
print(json.dumps(result))
"""

TIMEOUT_S = 30


def apply_variant(variant_path):
    """Copy the frozen fixture plus one candidate worker.py into an
    isolated temp dir. Returns the dir path (caller cleans up)."""
    work_dir = Path(tempfile.mkdtemp(prefix="retry-eval-"))
    shutil.copy(FIXTURE_DIR / "gateway.py", work_dir / "gateway.py")
    shutil.copy(variant_path, work_dir / "worker.py")
    (work_dir / "driver.py").write_text(DRIVER)
    return work_dir


def run_scenario(work_dir, script):
    """Run one scripted scenario in a subprocess. Returns the result dict,
    or {"timeout": True} if the variant hangs."""
    try:
        proc = subprocess.run(
            [sys.executable, "driver.py", json.dumps({"script": script})],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {"timeout": True}
    if proc.returncode != 0:
        return {"crashed": True, "stderr": proc.stderr[-500:]}
    return json.loads(proc.stdout)


def _keys(calls):
    return [c[1] for c in calls]


def score_variant(variant_path):
    """Apply one variant and score R1..R5. Returns
    {"checks": {name: bool}, "detail": {...}}."""
    variant_path = Path(variant_path)
    work_dir = apply_variant(variant_path)
    try:
        return _score_isolated(work_dir)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _score_isolated(work_dir):
    transient = run_scenario(work_dir, ["transient", "ok"])
    ambiguous = run_scenario(work_dir, ["transient_after_settle", "ok"])
    multi = run_scenario(work_dir, ["transient", "transient", "ok"])
    permanent = run_scenario(work_dir, ["permanent"])

    checks, detail = {}, {}

    # R1: key identical and present across all attempts of one batch.
    keys = _keys(transient.get("calls") or [])
    checks["R1_key_stable"] = (
        len(keys) >= 2 and all(k == "key-1" for k in keys)
    )
    detail["R1_keys"] = keys

    # R2: exactly one settlement when the first attempt commits but the
    # response is lost. A regenerated or missing key settles twice.
    checks["R2_no_duplicate"] = ambiguous.get("settled") == ["batch-1"]
    detail["R2_settled"] = ambiguous.get("settled")

    # R3: transient faults retried until success.
    checks["R3_transient_retried"] = (
        multi.get("raised") is None
        and multi.get("returned") is not None
        and len(multi.get("calls") or []) == 3
    )
    detail["R3_calls"] = len(multi.get("calls") or [])

    # R4: permanent fault raises without retrying.
    checks["R4_permanent_stops"] = (
        permanent.get("raised") == "PermanentError"
        and len(permanent.get("calls") or []) == 1
    )
    detail["R4"] = (permanent.get("raised"), len(permanent.get("calls") or []))

    # R5: retry lives only in the worker layer.
    checks["R5_single_retry_layer"] = (
        transient.get("client_max_retries") == 0
        and transient.get("client_retries") == 0
    )
    detail["R5"] = (
        transient.get("client_max_retries"),
        transient.get("client_retries"),
    )

    runs = (transient, ambiguous, multi, permanent)
    if any(r.get("timeout") or r.get("crashed") for r in runs):
        for k in checks:
            checks[k] = False
        detail["harness"] = "variant timed out or crashed"

    return {"checks": checks, "detail": detail}
