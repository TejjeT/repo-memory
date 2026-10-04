"""Mechanical evaluator for the retry/idempotency coding experiment.

No LLM policy decisions anywhere: each candidate variant is a ``worker.py``
replacement applied to an isolated copy of the frozen fixture, then
exercised against scripted gateway scenarios in a subprocess. Every check
is a deterministic predicate over recorded gateway calls.

The driver reports through a result file (``result.json``), never through
stdout: candidate print/debug output cannot corrupt the result protocol.
A missing or malformed result is a recorded harness failure, not a crash.

Rubric (predeclared):
  R1 key_stable          -- the idempotency key is identical (and present)
                            across all submit attempts of one batch, the
                            submitted key is the caller-provided key, and
                            two distinct batches on one gateway settle under
                            their own keys
  R2 no_duplicate        -- a transient failure settles the batch exactly
                            once AND the worker returns the settled
                            response (no swallowed ambiguous failure)
  R3 transient_retried   -- transient faults are retried until success;
                            clean submissions return the settled response
                            with no exception
  R4 permanent_stops     -- a permanent fault raises without retrying
  R5 single_retry_layer  -- retry lives only in the worker layer: the
                            gateway/client layer must stay disabled AND
                            unexercised
"""

import json
import shutil
import subprocess
import sys
import tempfile
from contextlib import suppress
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_DIR = HERE.parent / "fixture"
RESULT_FILE = "result.json"

DRIVER = """\
import json, sys
from gateway import FakeGateway, TransientError, PermanentError
import worker

scenario = json.loads(sys.argv[1])
gateway = FakeGateway(scenario["script"])
client = worker.make_client(gateway)
batch_results = []
for b in scenario["batches"]:
    calls_before = len(gateway.calls)
    settled_before = len(gateway.settled)
    r = {
        "batch_id": b["batch_id"],
        "key": b["key"],
        "returned": None,
        "raised": None,
        "new_calls": None,
        "new_settled": None,
    }
    try:
        r["returned"] = worker.settle_batch(
            client, b["batch_id"], {"amount": 100}, b["key"]
        )
    except Exception as e:  # noqa: BLE001 -- the fixture must surface faults
        r["raised"] = type(e).__name__
    r["new_calls"] = [list(c) for c in gateway.calls[calls_before:]]
    r["new_settled"] = gateway.settled[settled_before:]
    batch_results.append(r)
result = {
    "batch_results": batch_results,
    "calls": [list(c) for c in gateway.calls],
    "settled": list(gateway.settled),
    "client_max_retries": client.max_retries,
    "client_retries": client.client_retries,
}
with open("result.json", "w") as f:
    json.dump(result, f)
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


def _validate_result(work_dir):
    """Read the driver's result file. Returns (result, error): exactly one
    is non-None. Candidate stdout is never parsed as protocol."""
    path = work_dir / RESULT_FILE
    try:
        result = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, f"result unreadable: {type(e).__name__}"
    if not isinstance(result, dict) or not isinstance(
        result.get("batch_results"), list
    ):
        return None, "result malformed: expected dict with batch_results"
    return result, None


def run_scenario(work_dir, script, batches):
    """Run one scripted scenario in a subprocess. Returns the result dict,
    or a dict with one of "timeout", "crashed", "harness_error" set.

    A stale result file from a previous scenario must never be mistaken
    for this run's output, so it is removed before executing.
    """
    result_path = work_dir / RESULT_FILE
    with suppress(OSError):
        result_path.unlink()
    try:
        proc = subprocess.run(
            [sys.executable, "driver.py", json.dumps({"script": script, "batches": batches})],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {"timeout": True}
    if proc.returncode != 0:
        return {
            "crashed": True,
            "stderr": proc.stderr[-500:],
            "stdout_tail": proc.stdout[-500:],
        }
    result, error = _validate_result(work_dir)
    if error is not None:
        return {"harness_error": error, "stdout_tail": proc.stdout[-500:]}
    # Candidate stdout is protocol-separated; keep a tail for debugging.
    result["candidate_stdout_tail"] = proc.stdout[-500:]
    return result


def score_variant(variant_path):
    """Apply one variant and score R1..R5. Returns
    {"checks": {name: bool}, "detail": {...}}."""
    variant_path = Path(variant_path)
    work_dir = apply_variant(variant_path)
    try:
        return _score_isolated(work_dir)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _batch0(result):
    batches = result.get("batch_results") or []
    return batches[0] if batches else {}


def _completed_cleanly(result, batch_id):
    """The worker returned the gateway's settled response and raised
    nothing: a swallowed ambiguous failure or a spurious raise fails."""
    br = _batch0(result)
    return (
        br.get("batch_id") == batch_id
        and br.get("raised") is None
        and br.get("returned") == {"status": "settled", "batch_id": batch_id}
    )


def _score_isolated(work_dir):
    one = [{"batch_id": "batch-1", "key": "key-1"}]
    clean = run_scenario(work_dir, ["ok"], one)
    transient = run_scenario(work_dir, ["transient", "ok"], one)
    ambiguous = run_scenario(work_dir, ["transient_after_settle", "ok"], one)
    multi = run_scenario(work_dir, ["transient", "transient", "ok"], one)
    permanent = run_scenario(work_dir, ["permanent"], one)
    two_batch = run_scenario(
        work_dir,
        ["ok", "ok"],
        [
            {"batch_id": "batch-A", "key": "key-A"},
            {"batch_id": "batch-B", "key": "key-B"},
        ],
    )

    checks, detail = {}, {}

    # R1: key identical and present across all attempts of one batch, the
    # submitted key is the caller-provided key, and two distinct batches
    # on one gateway settle under their own keys (catches hardcoded keys).
    t_keys = [c[1] for c in transient.get("calls", [])]
    r1_single = len(t_keys) >= 2 and all(k == "key-1" for k in t_keys)
    tb = two_batch.get("batch_results") or []
    r1_cross = (
        len(tb) == 2
        and all(
            br.get("new_calls")
            and all(
                c[0] == br["batch_id"] and c[1] == br["key"]
                for c in br["new_calls"]
            )
            for br in tb
        )
        and two_batch.get("settled") == ["batch-A", "batch-B"]
    )
    checks["R1_key_stable"] = bool(r1_single and r1_cross)
    detail["R1_single_keys"] = t_keys
    detail["R1_cross_settled"] = two_batch.get("settled")

    # R2: exactly one settlement when the first attempt commits but the
    # response is lost, and the worker returns the settled response (a
    # swallowed ambiguous failure is not a success).
    checks["R2_no_duplicate"] = bool(
        ambiguous.get("settled") == ["batch-1"]
        and _completed_cleanly(ambiguous, "batch-1")
    )
    detail["R2_settled"] = ambiguous.get("settled")
    detail["R2_returned"] = _batch0(ambiguous).get("returned")
    detail["R2_raised"] = _batch0(ambiguous).get("raised")

    # R3: transient faults retried until success, and clean submissions
    # return the settled response with no exception.
    checks["R3_transient_retried"] = bool(
        _completed_cleanly(clean, "batch-1")
        and _completed_cleanly(transient, "batch-1")
        and _completed_cleanly(multi, "batch-1")
        and len(multi.get("calls", [])) == 3
    )
    detail["R3_calls"] = len(multi.get("calls", []))

    # R4: permanent fault raises without retrying.
    p0 = _batch0(permanent)
    checks["R4_permanent_stops"] = bool(
        p0.get("raised") == "PermanentError"
        and len(permanent.get("calls", [])) == 1
    )
    detail["R4"] = (p0.get("raised"), len(permanent.get("calls", [])))

    # R5: retry lives only in the worker layer.
    checks["R5_single_retry_layer"] = bool(
        transient.get("client_max_retries") == 0
        and transient.get("client_retries") == 0
    )
    detail["R5"] = (
        transient.get("client_max_retries"),
        transient.get("client_retries"),
    )

    runs = {
        "clean": clean,
        "transient": transient,
        "ambiguous": ambiguous,
        "multi": multi,
        "permanent": permanent,
        "two_batch": two_batch,
    }
    broken = {
        name: {k: r[k] for k in ("timeout", "crashed", "harness_error") if k in r}
        for name, r in runs.items()
        if r.get("timeout") or r.get("crashed") or r.get("harness_error")
    }
    if broken:
        for k in checks:
            checks[k] = False
        detail["harness"] = broken

    return {"checks": checks, "detail": detail}
