"""Synthetic harness checks, never measured coding-agent trial evidence."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

EXP = Path(__file__).resolve().parents[1] / "research/experiments/policy-routing"
REFERENCE = """\
from typing import NamedTuple
class RetryPlan(NamedTuple):
    gateway_attempts: int
    worker_attempts: int
def retry_plan(repository):
    if repository == "clearing-adapter":
        return RetryPlan(3, 1)
    if repository in ("payment-worker", "reconciliation-worker"):
        return RetryPlan(1, 3)
    raise ValueError(repository)
"""


def load(name):
    spec = importlib.util.spec_from_file_location(f"routing_{name}", EXP / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runner():
    return load("run")


@pytest.fixture
def bundle(tmp_path, runner):
    # This program deliberately emits the test oracle. It validates collection
    # mechanics only; it is not a model and must never be reported as one.
    worker = tmp_path / "synthetic_worker.py"
    worker.write_text(
        "import json, sys\njob = json.loads(sys.stdin.readline())\n"
        "if job['tools']:\n"
        "    for name, args in [('memory_search', {'repository':'clearing-adapter'}),\n"
        "                       ('memory_get', {'assertion_id':'EA-ROUTE-OLD'})]:\n"
        "        print(json.dumps({'type':'tool_call','name':name,'arguments':args}),flush=True)\n"
        "        reply = json.loads(sys.stdin.readline())\n"
        "        assert not reply['is_error']\n"
        f"code = {REFERENCE!r}\n"
        "print(json.dumps({'type':'final','code':code,'citations':[],\n"
        "                  'metadata':{'synthetic_test':True}}),flush=True)\n"
    )
    return runner.prepare(tmp_path / "bundle", [sys.executable, str(worker)], "synthetic-test")


def test_reference_and_starting_fixture_discriminate():
    rubric = load("rubric")
    assert rubric.evaluate(REFERENCE)["pass"]
    assert not rubric.evaluate((EXP / "fixture/policy.py").read_text())["pass"]


@pytest.mark.parametrize(
    "code",
    [
        REFERENCE.replace("RetryPlan(3, 1)", "RetryPlan(1, 3)"),  # loses exception
        REFERENCE.replace("RetryPlan(1, 3)", "RetryPlan(3, 3)"),  # stale dual layer
        REFERENCE.replace("RetryPlan(1, 3)", "RetryPlan(1, 1)"),  # analytics scope
        REFERENCE.replace("RetryPlan(3, 1)", "RetryPlan(True, 3)"),
        REFERENCE.replace("raise ValueError(repository)", "return RetryPlan(1, 3)"),
        'raise RuntimeError("candidate failed")',
        'open("observed.json", "w").write("[]"); raise SystemExit(0)',
    ],
)
def test_invalid_patches_fail(code):
    assert not load("rubric").evaluate(code)["pass"]


def test_fair_inputs_and_no_fixture_answer_cue(bundle, runner):
    manifest = runner.verify_bundle(bundle)
    jobs = {
        arm: runner.read_json(bundle / "trials" / f"{arm}-r1/job.json") for arm in runner.CONDITIONS
    }
    assert jobs["repo-only"]["files"] == jobs["generic-retrieval"]["files"]
    assert jobs["repo-only"]["files"] == jobs["repo-memory"]["files"]
    assert jobs["repo-only"]["documents"] == []
    assert jobs["generic-retrieval"]["documents"] == jobs["repo-memory"]["documents"]
    assert jobs["generic-retrieval"]["documents"]
    assert not load("rubric").leaks(jobs)
    fixture = jobs["repo-only"]["files"]["policy.py"]
    assert "clearing-adapter" not in fixture
    assert "supersed" not in fixture.lower()
    assert len({j["trial_id"] for j in manifest["jobs"].values()}) == 9


def test_rehashed_payload_cannot_omit_generic_sources(bundle, runner):
    path = bundle / "trials/generic-retrieval-r1/job.json"
    job = runner.read_json(path)
    job["documents"] = []
    path.write_text(json.dumps(job))
    manifest = runner.read_json(bundle / "manifest.json")
    manifest["jobs"]["generic-retrieval-r1"]["job_sha256"] = runner.digest(path)
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="payload differs"):
        runner.verify_bundle(bundle)


def test_snapshot_hash_omission_fails(bundle, runner):
    manifest = runner.read_json(bundle / "manifest.json")
    del manifest["files"]["snapshot/experiment/assertions.json"]
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="incomplete snapshot"):
        runner.verify_bundle(bundle)


def test_synthetic_full_collection_uses_live_mcp_and_assigned_denominators(bundle, runner):
    for name in runner.verify_bundle(bundle)["order"]:
        assert asyncio.run(runner.collect_trial(bundle, name)) == "completed"
    report = runner.score(bundle)
    assert all(
        row == {"assigned": 3, "completed": 3, "passed": 3} for row in report["summary"].values()
    )
    assert all(
        row["worker_reported_metadata"]["synthetic_test"] for row in report["results"].values()
    )
    for run in range(1, 4):
        receipt = runner.read_json(bundle / f"trials/repo-memory-r{run}/receipt.json")
        assert receipt["tool_calls"] == 2
        assert receipt["binding_type"] == "collection-hook"
        assert "invocation.json" in receipt["files"]
    untouched = (EXP.parent / "supersession/trial_mcp/REPORT.md").read_text()
    assert "repo-memory had one incomplete trial" in untouched


def test_missing_trials_stay_assigned(bundle, runner):
    report = runner.score(bundle)
    assert all(
        row == {"assigned": 3, "completed": 0, "passed": 0} for row in report["summary"].values()
    )


@pytest.mark.parametrize(
    "artifact",
    ["worker.stdin", "worker.stdout", "response.json", "transport.jsonl", "invocation.json"],
)
def test_collected_artifact_drift_is_rejected(bundle, runner, artifact):
    asyncio.run(runner.collect_trial(bundle, "repo-only-r1"))
    with (bundle / "trials/repo-only-r1" / artifact).open("a") as stream:
        stream.write("tampered")
    row = runner.score(bundle)["results"]["repo-only-r1"]
    assert row["status"] == "invalid_evidence"
    assert not row["pass"]


@pytest.mark.parametrize(
    "bad_line,status", [("not json", "protocol_error"), ("", "protocol_error")]
)
def test_raw_failure_is_preserved(tmp_path, runner, bad_line, status):
    worker = tmp_path / "bad_worker.py"
    worker.write_text(f"print({bad_line!r})\n")
    root = runner.prepare(tmp_path / "bad", [sys.executable, str(worker)], "synthetic-test")
    assert asyncio.run(runner.collect_trial(root, "repo-only-r1")) == status
    assert (root / "trials/repo-only-r1/worker.stdout").read_text() == bad_line + "\n"
    assert runner.score(root)["summary"]["repo-only"]["passed"] == 0


def test_collected_trial_cannot_be_overwritten(bundle, runner):
    asyncio.run(runner.collect_trial(bundle, "repo-only-r1"))
    with pytest.raises(FileExistsError):
        asyncio.run(runner.collect_trial(bundle, "repo-only-r1"))


def test_abstention_is_complete_but_unsolved(tmp_path, runner):
    worker = tmp_path / "abstain.py"
    worker.write_text(
        'print(\'{"type":"abstain","reason":"policy unavailable","citations":[]}\')\n'
    )
    root = runner.prepare(tmp_path / "abstain", [sys.executable, str(worker)], "synthetic-test")
    asyncio.run(runner.collect_trial(root, "repo-only-r1"))
    assert runner.score(root)["summary"]["repo-only"] == {
        "assigned": 3,
        "completed": 1,
        "passed": 0,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("binding_type", "posthoc"),
        ("execution_id", "wrong-worker"),
        ("trial_id", "wrong-trial"),
        ("elapsed_seconds", -1),
        ("status", "pretend-completed"),
    ],
)
def test_invalid_receipt_metadata_cannot_pass(bundle, runner, field, value):
    asyncio.run(runner.collect_trial(bundle, "repo-only-r1"))
    path = bundle / "trials/repo-only-r1/receipt.json"
    receipt = runner.read_json(path)
    receipt[field] = value
    path.write_text(json.dumps(receipt))
    row = runner.score(bundle)["results"]["repo-only-r1"]
    assert row["status"] == "invalid_evidence"
    assert not row["pass"]


@pytest.mark.parametrize(
    "citation,extra_code",
    [
        ("doc://not-delivered", ""),
        (None, "\n# incident://ROUTE-INC-17\n"),
    ],
)
def test_correct_patch_with_bad_provenance_fails(tmp_path, runner, citation, extra_code):
    worker = tmp_path / "leaky.py"
    final = {
        "type": "final",
        "code": REFERENCE + extra_code,
        "citations": [citation] if citation else [],
    }
    worker.write_text(f"print({json.dumps(final)!r})\n")
    root = runner.prepare(tmp_path / "leaky", [sys.executable, str(worker)], "synthetic-test")
    asyncio.run(runner.collect_trial(root, "repo-only-r1"))
    assert not runner.score(root)["results"]["repo-only-r1"]["pass"]


def test_memory_arm_without_transport_use_is_unqualified(tmp_path, runner):
    worker = tmp_path / "no_tools.py"
    worker.write_text(
        f"print({json.dumps({'type': 'final', 'code': REFERENCE, 'citations': []})!r})\n"
    )
    root = runner.prepare(tmp_path / "no-tools", [sys.executable, str(worker)], "synthetic-test")
    assert asyncio.run(runner.collect_trial(root, "repo-memory-r1")) == "completed"
    row = runner.score(root)["results"]["repo-memory-r1"]
    assert row["completed"]
    assert not row["pass"]


def test_timeout_has_collection_receipt_and_partial_output(tmp_path, runner):
    worker = tmp_path / "slow.py"
    worker.write_text("import time\nprint('partial', end='', flush=True)\ntime.sleep(5)\n")
    root = runner.prepare(
        tmp_path / "slow", [sys.executable, str(worker)], "synthetic-test", timeout=0.3
    )
    assert asyncio.run(runner.collect_trial(root, "repo-only-r1")) == "timeout"
    assert (root / "trials/repo-only-r1/worker.stdout").read_text() == "partial"
    assert runner.score(root)["results"]["repo-only-r1"]["status"] == "timeout"


def test_worker_command_source_drift_rejected_before_launch(bundle, runner):
    command = runner.read_json(bundle / "manifest.json")["command"]
    with Path(command[1]).open("a") as stream:
        stream.write("\n# changed adapter\n")
    with pytest.raises(ValueError, match="command files changed"):
        asyncio.run(runner.collect_trial(bundle, "repo-only-r1"))
