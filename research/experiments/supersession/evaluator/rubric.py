"""Mechanical evaluator for the supersession coding experiment (issue #5).

No LLM policy decisions anywhere: each candidate variant is a ``worker.py``
replacement applied to an isolated copy of the frozen fixture, then
exercised against scripted gateway scenarios in a subprocess. Every check
is a deterministic predicate.

The driver reports through a result file (``result.json``), never through
stdout: candidate print/debug output cannot corrupt the result protocol.
A missing or malformed result is a recorded harness failure, not a crash.

Rubric (predeclared):
  S1 current_compliance -- gateway max_retries is 0 (EA-006: exactly one
                          retry layer, worker-owned)
  S2 stale_rejected     -- gateway max_retries is not 3 (the superseded
                          EA-005 value)
  S3 single_layer       -- a transient fault is retried to success by the
                          worker layer while the gateway layer stays
                          disabled AND unexercised
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
r = {
    "gateway_max_retries": worker.GATEWAY_MAX_RETRIES,
    "client_max_retries": client.max_retries,
    "returned": None,
    "raised": None,
    "client_retries": None,
    "gateway_calls": None,
}
try:
    r["returned"] = worker.settle_batch(
        client, "B1", {"amount": 100}, "key-1"
    )
except Exception as e:  # noqa: BLE001 -- the fixture must surface faults
    r["raised"] = type(e).__name__
r["client_retries"] = client.client_retries
r["gateway_calls"] = len(gateway.calls)
with open("result.json", "w") as f:
    json.dump(r, f)
"""

TIMEOUT_S = 30

# The stale EA-005 value. S2 fails if a variant keeps it.
STALE_GATEWAY_RETRIES = 3


def apply_variant(variant_path):
    """Copy the frozen fixture plus one candidate worker.py into an
    isolated temp dir. Returns the dir path (caller cleans up)."""
    work_dir = Path(tempfile.mkdtemp(prefix="supersession-eval-"))
    shutil.copy(FIXTURE_DIR / "gateway.py", work_dir / "gateway.py")
    shutil.copy(variant_path, work_dir / "worker.py")
    (work_dir / "driver.py").write_text(DRIVER)
    return work_dir


def _validate_result(work_dir):
    """Read the driver's result file. Returns (result, error): exactly one
    is non-None. Candidate stdout is never parsed as protocol."""
    path = work_dir / RESULT_FILE
    try:
        return json.loads(path.read_text()), None
    except Exception as e:  # noqa: BLE001 -- malformed result is a finding
        return None, f"harness: unreadable result: {e}"


def _run_scenario(work_dir, script):
    """Run one scripted scenario. Returns (result, error).

    The previous result file is deleted first: a driver that crashes
    without writing must not be scored from a stale result.
    """
    with suppress(FileNotFoundError):
        (work_dir / RESULT_FILE).unlink()
    try:
        subprocess.run(
            [sys.executable, "driver.py", json.dumps({"script": script})],
            cwd=work_dir,
            capture_output=True,
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return None, "harness: driver timeout (possible runaway retry loop)"
    return _validate_result(work_dir)


def evaluate(variant_path):
    """Score one candidate worker.py. Returns a dict of check results."""
    work_dir = apply_variant(variant_path)
    try:
        # S1/S2 are static: read the configured gateway retry value.
        result, error = _run_scenario(work_dir, ["ok"])
        if error:
            return {"error": error, "S1": False, "S2": False, "S3": False}
        gateway_retries = result["gateway_max_retries"]
        s1 = gateway_retries == 0
        s2 = gateway_retries != STALE_GATEWAY_RETRIES

        # S3: transient fault must be retried to success by the worker
        # while the gateway layer stays disabled and unexercised. The
        # batch must actually reach the gateway: a worker that never
        # submits cannot pass on a fabricated return value.
        result, error = _run_scenario(
            work_dir, ["transient", "transient", "ok"]
        )
        if error:
            return {
                "error": error,
                "S1": s1,
                "S2": s2,
                "S3": False,
            }
        s3 = (
            result["raised"] is None
            and result["returned"] is not None
            and result["gateway_calls"] is not None
            and result["gateway_calls"] > 0
            and result["client_max_retries"] == 0
            and result["client_retries"] == 0
        )
        return {"S1": s1, "S2": s2, "S3": s3}
    finally:
        with suppress(Exception):
            shutil.rmtree(work_dir)


# ---------------------------------------------------------------------------
# Restricted-identifier scan for MCP-delivered context.
# ---------------------------------------------------------------------------

#: Identifiers that must never appear in context delivered to the agent.
RESTRICTED_MARKERS = ("INC-463", "incident://")


def scan_restricted(payload):
    """Return restricted markers found in a serialized MCP response.

    Empty means clean. The payload is stringified; any occurrence of a
    restricted identifier or incident URI scheme is a leak.
    """
    text = json.dumps(payload)
    return [marker for marker in RESTRICTED_MARKERS if marker in text]


if __name__ == "__main__":
    variant = Path(sys.argv[1])
    print(json.dumps(evaluate(variant), indent=2))
