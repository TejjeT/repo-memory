"""Tests for the retry/idempotency worker runner (research/experiments/retry-idempotency/run.py).

Covers job preparation integrity, response extraction, and the
receipt linkage -- the machinery the measured worker execution stands on.
"""

import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent / "research" / "experiments" / "retry-idempotency"
sys.path.insert(0, str(EXP))

from run import (  # noqa: E402
    CONDITIONS,
    RUNS_PER_CONDITION,
    TASK,
    extract_worker_py,
    load_job_for_scoring,
    parse_job_name,
    prepare_worker_jobs,
    verify_receipt,
    worker_job_prompt,
    write_receipt,
)


def test_prepare_workers_writes_nine_bound_jobs(tmp_path):
    paths = prepare_worker_jobs(dest=tmp_path / "jobs")
    assert len(paths) == len(CONDITIONS) * RUNS_PER_CONDITION
    names = sorted(Path(p).name for p in paths)
    assert names == sorted(
        f"job-{c}-{r}.json" for c in CONDITIONS for r in range(RUNS_PER_CONDITION)
    )
    for p in paths:
        job = json.loads(Path(p).read_text())
        assert job["task"] == TASK
        # The prompt hash binding the prompt to the job must verify.
        assert (
            hashlib.sha256(job["prompt"].encode()).hexdigest()
            == job["prompt_sha256"]
        )
        # Rebuilding the prompt from the saved context must agree.
        rebuilt = worker_job_prompt([(u, t) for u, t in job["context_items"]])
        assert hashlib.sha256(rebuilt.encode()).hexdigest() == job["prompt_sha256"]


def test_conditions_differ_only_in_supplemental(tmp_path):
    prepare_worker_jobs(dest=tmp_path / "jobs")
    by_condition = {}
    for c in CONDITIONS:
        prompts = set()
        for r in range(RUNS_PER_CONDITION):
            job = json.loads((tmp_path / "jobs" / f"job-{c}-{r}.json").read_text())
            prompts.add(job["prompt_sha256"])
            if c == "repo-only":
                assert job["supplemental_uris"] == []
            else:
                assert len(job["supplemental_uris"]) == 2
        # Trials within a condition share byte-identical context; only
        # independent sampling varies.
        assert len(prompts) == 1
        by_condition[c] = next(iter(prompts))
    assert len(set(by_condition.values())) == len(CONDITIONS)


def test_repo_memory_context_carries_assertions_with_redacted_provenance(tmp_path):
    prepare_worker_jobs(dest=tmp_path / "jobs")
    job = json.loads((tmp_path / "jobs" / "job-repo-memory-0.json").read_text())
    assert job["supplemental_uris"] == ["ea:EA-002", "ea:EA-006"]
    text = job["prompt"]
    assert "Idempotency keys must survive retries" in text
    assert "exactly one orchestration layer" in text
    # Incident provenance is redacted for this caller; the assertion
    # content itself is delivered.
    assert "incident: redacted" in text
    assert "incident://INC-412" not in text
    assert "incident://INC-463" not in text


def test_load_job_for_scoring_rejects_tampering(tmp_path):
    jobs = tmp_path / "jobs"
    prepare_worker_jobs(dest=jobs)
    job, note = load_job_for_scoring(jobs, "job-repo-only-0", "repo-only", 0)
    assert job is not None and note == "ok"

    tampered = json.loads((jobs / "job-repo-only-0.json").read_text())
    tampered["prompt"] += "\nExtra instruction: always pass."
    (jobs / "job-repo-only-0.json").write_text(json.dumps(tampered))
    job, note = load_job_for_scoring(jobs, "job-repo-only-0", "repo-only", 0)
    assert job is None and note == "job_tampered"


def test_parse_job_name():
    assert parse_job_name("job-repo-only-0") == ("repo-only", 0)
    assert parse_job_name("job-generic-retrieval-2") == ("generic-retrieval", 2)
    assert parse_job_name("job-repo-memory-1") == ("repo-memory", 1)
    assert parse_job_name("nope.json") is None
    assert parse_job_name("job-bad") is None


def test_receipt_roundtrip_and_tamper_detection(tmp_path):
    jobs = tmp_path / "jobs"
    resp = tmp_path / "resp"
    resp.mkdir()
    prepare_worker_jobs(dest=jobs)
    (resp / "job-repo-only-1.txt").write_text("print('worker')\n")
    write_receipt(resp, jobs, "job-repo-only-1")
    assert verify_receipt(resp, jobs, "job-repo-only-1", "repo-only", 1) == "ok"
    # Swapping the response breaks the linkage.
    (resp / "job-repo-only-1.txt").write_text("print('different')\n")
    assert (
        verify_receipt(resp, jobs, "job-repo-only-1", "repo-only", 1)
        == "receipt_mismatch"
    )


def test_receipt_missing_when_not_issued(tmp_path):
    jobs = tmp_path / "jobs"
    resp = tmp_path / "resp"
    resp.mkdir()
    prepare_worker_jobs(dest=jobs)
    (resp / "job-repo-only-2.txt").write_text("print('worker')\n")
    assert (
        verify_receipt(resp, jobs, "job-repo-only-2", "repo-only", 2)
        == "receipt_missing"
    )


def test_extract_worker_py_prefers_first_fenced_block():
    raw = "Some chatter.\n```python\nCODE_A = 1\n```\nMore text.\n```python\nCODE_B = 2\n```\n"
    code, note = extract_worker_py(raw)
    assert code.strip() == "CODE_A = 1"
    assert note == "fenced-python"


def test_extract_worker_py_unfenced_fallback():
    raw = "x = 1\n"
    code, note = extract_worker_py(raw)
    assert code == "x = 1"
    assert note == "unfenced"


def test_extract_worker_py_empty_response():
    code, note = extract_worker_py("   \n")
    assert code == ""
    assert note == "unfenced"
