"""Regression checks for the saved-trial evidence gates."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

EXP = Path(__file__).resolve().parents[1] / "research/experiments/supersession"


@pytest.fixture
def runner(tmp_path, monkeypatch):
    rubric_spec = importlib.util.spec_from_file_location("rubric", EXP / "evaluator/rubric.py")
    rubric = importlib.util.module_from_spec(rubric_spec)
    monkeypatch.setitem(sys.modules, "rubric", rubric)
    rubric_spec.loader.exec_module(rubric)
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = importlib.util.spec_from_file_location("supersession_runner", EXP / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shutil.copytree(EXP / "runs", tmp_path / "runs")
    module.ROOT = tmp_path
    return module


def change(path, **updates):
    data = json.loads(path.read_text())
    data.update(updates)
    path.write_text(json.dumps(data))


@pytest.mark.parametrize("binding", [None, "", "bad-hash"])
def test_invalid_binding_fails(runner, binding):
    name = "repo-only-r1"
    receipt = runner.ROOT / "runs/receipts" / runner.receipt_name(name)
    change(receipt, prompt_sha256=binding)
    assert not runner.verify_receipt(runner.ROOT / "runs/worker-responses" / name, name)[0]


@pytest.mark.parametrize("rehash", [False, True])
def test_changed_prompt_fails(runner, rehash):
    name = "repo-only-r1"
    job = runner.ROOT / "runs/worker-jobs" / f"{name}.json"
    updates = {"prompt": "changed delivery"}
    if rehash:
        updates["prompt_sha256"] = runner.sha256_text(updates["prompt"])
    change(job, **updates)
    assert not runner.verify_receipt(runner.ROOT / "runs/worker-responses" / name, name)[0]


@pytest.mark.parametrize("field,value", [
    ("job_name", "wrong"), ("experiment", "wrong"),
    ("condition", "repo-memory"), ("run", 99), ("task", "wrong"),
])
def test_wrong_identity_fails(runner, field, value):
    job = runner.ROOT / "runs/worker-jobs/repo-only-r1.json"
    change(job, **{field: value})
    assert not runner.verify_job_inputs()[0]


@pytest.mark.parametrize("job_name", ["repo-only-r1", "repo-memory-r3"])
@pytest.mark.parametrize("empty", [False, True])
def test_incomplete_manifest_fails(runner, job_name, empty):
    path = runner.ROOT / "runs/worker-jobs" / f"{job_name}.json"
    job = json.loads(path.read_text())
    hashes = job["manifest"]["input_hashes"]
    job["manifest"]["input_hashes"] = {} if empty else dict([next(iter(hashes.items()))])
    path.write_text(json.dumps(job))
    assert not runner.verify_job_inputs()[0]


def test_forced_replacement_retains_predecessor(runner):
    name = "repo-only-r1"
    dest = runner.ROOT / "runs/receipts"
    old = json.loads((dest / runner.receipt_name(name)).read_text())
    response = runner.ROOT / "runs/worker-responses" / name
    with pytest.raises(ValueError, match="reason"):
        runner.write_receipt(response, name, "replacement", force=True)
    runner.write_receipt(response, name, "replacement", force=True, reason="test re-issue")
    event = json.loads((dest / "audit.log").read_text().splitlines()[-1])
    assert event["old_receipt"] == old
    assert event["new_response_sha256"] == runner.sha256_text("replacement")
    assert event["new_binding_type"] == "posthoc"


def test_replay_labels_posthoc_receipts(runner):
    report = runner.score_worker_responses()
    assert report["evidence_type"] == "replay"
    assert all(trial["receipt"]["binding_type"] == "posthoc"
               for trial in report["results"].values())
    assert all(result["passed"] == 3 for result in report["summary"].values())
