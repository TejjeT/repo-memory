"""Evidence failures must not disappear from the transport trial results."""

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
    spec = importlib.util.spec_from_file_location(
        "mcp_trial_runner", EXP / "trial_mcp/run_mcp_trials.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shutil.copytree(EXP / "trial_mcp", tmp_path / "trial")
    module.ROOT = tmp_path / "trial"
    return module


def rewrite_receipt(runner, **updates):
    path = runner.ROOT / "receipts/receipt-repo-only-r1.json"
    receipt = json.loads(path.read_text())
    receipt.update(updates)
    path.write_text(json.dumps(receipt))


def test_saved_batch_keeps_assigned_denominator(runner, capsys):
    assert runner.score_trials() == 0
    output = capsys.readouterr().out
    assert "repo-memory-r2: NO_RECEIPT" in output
    assert "repo-memory: 2/3 assigned trials passed" in output


@pytest.mark.parametrize("updates", [
    {"job_name": "wrong"}, {"experiment": "wrong"},
    {"captured_at": "not-a-date"}, {"binding_type": "wrong"},
    {"brief_sha256": "0" * 64}, {"response_sha256": "bad-hash"},
    {"response_bytes": -1}, {"response_bytes": True},
])
def test_bad_receipt_fails_command(runner, updates):
    rewrite_receipt(runner, **updates)
    assert runner.score_trials() == 1


@pytest.mark.parametrize("path", [
    "briefs/repo-only-r1.md", "briefs/repo-only-r1.manifest.json",
    "responses/repo-only-r1/response.md", "receipts/receipt-repo-only-r1.json",
])
def test_missing_evidence_fails_command(runner, path):
    (runner.ROOT / path).unlink()
    assert runner.score_trials() == 1


def test_nonobject_receipt_fails_command(runner):
    (runner.ROOT / "receipts/receipt-repo-only-r1.json").write_text("[]")
    assert runner.score_trials() == 1


@pytest.mark.parametrize("suffix", ["", "\nincident://INC-463"])
def test_crashing_or_leaking_response_fails(runner, suffix, capsys):
    raw = '```python\n# GATEWAY_MAX_RETRIES = 0\nraise RuntimeError("broken")\n```' + suffix
    (runner.ROOT / "responses/repo-only-r1/response.md").write_text(raw)
    rewrite_receipt(runner, response_sha256=runner.sha256_text(raw),
                    response_bytes=len(raw.encode()))
    assert runner.score_trials() == 1
    output = capsys.readouterr().out
    expected = "repo-only-r1: FAIL_LEAK" if suffix else "repo-only-r1: FAIL"
    assert expected in output


def test_stray_incomplete_trial_response_fails(runner):
    path = runner.ROOT / "responses/repo-memory-r2/response.md"
    path.parent.mkdir()
    path.write_text("unreceipted response")
    assert runner.score_trials() == 1


def test_context_leak_fails(runner):
    path = runner.ROOT / "briefs/repo-only-r1.md"
    text = path.read_text() + "\nincident://INC-463"
    path.write_text(text)
    digest = runner.sha256_text(text)
    manifest_path = path.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text())
    manifest["brief_sha256"] = digest
    manifest_path.write_text(json.dumps(manifest))
    rewrite_receipt(runner, brief_sha256=digest)
    assert runner.score_trials() == 1
