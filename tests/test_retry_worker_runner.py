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
    ReceiptConflictError,
    extract_worker_py,
    load_job_for_scoring,
    parse_job_name,
    prepare_worker_jobs,
    score_worker_responses,
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
            elif c == "generic-retrieval":
                assert job["supplemental_uris"] == [
                    "corpus/retry-policy.md",
                    "corpus/idempotency-guide.md",
                ]
            elif c == "repo-memory":
                # Both retrieval arms share the ordinary documents; the
                # memory arm additionally carries the structured assertions.
                assert job["supplemental_uris"] == [
                    "corpus/retry-policy.md",
                    "corpus/idempotency-guide.md",
                    "ea:EA-002",
                    "ea:EA-006",
                ]
        # Trials within a condition share byte-identical context; only
        # independent sampling varies.
        assert len(prompts) == 1
        by_condition[c] = next(iter(prompts))
    assert len(set(by_condition.values())) == len(CONDITIONS)


def test_both_retrieval_arms_share_ordinary_documents(tmp_path):
    """The arms differ in delivery form (documents vs assertions), not in
    permitted facts: the memory arm must include the shared corpus."""
    prepare_worker_jobs(dest=tmp_path / "jobs")
    generic = json.loads((tmp_path / "jobs" / "job-generic-retrieval-0.json").read_text())
    memory = json.loads((tmp_path / "jobs" / "job-repo-memory-0.json").read_text())
    generic_docs = [u for u in generic["supplemental_uris"] if u.startswith("corpus/")]
    memory_docs = [u for u in memory["supplemental_uris"] if u.startswith("corpus/")]
    assert generic_docs == memory_docs != []
    # And the delivered text matches.
    generic_text = dict(generic["context_items"])
    memory_text = dict(memory["context_items"])
    for uri in generic_docs:
        assert memory_text[uri] == generic_text[uri]


def test_repo_memory_context_carries_assertions_with_redacted_provenance(tmp_path):
    prepare_worker_jobs(dest=tmp_path / "jobs")
    job = json.loads((tmp_path / "jobs" / "job-repo-memory-0.json").read_text())
    assert job["supplemental_uris"] == [
        "corpus/retry-policy.md",
        "corpus/idempotency-guide.md",
        "ea:EA-002",
        "ea:EA-006",
    ]
    text = job["prompt"]
    assert "Idempotency keys must survive retries" in text
    assert "exactly one orchestration layer" in text
    # Incident provenance is redacted for this caller; the assertion
    # content itself is delivered.
    assert "incident: redacted" in text
    assert "incident://INC-412" not in text
    assert "incident://INC-463" not in text


def test_repo_memory_context_withholds_incident_rationale(tmp_path):
    """The assertion rationale carries restricted incident background
    (INC-412); it must not reach workers in any arm."""
    prepare_worker_jobs(dest=tmp_path / "jobs")
    job = json.loads((tmp_path / "jobs" / "job-repo-memory-0.json").read_text())
    text = job["prompt"]
    assert "INC-412" not in text
    assert "INC-463" not in text
    assert "retry metadata was regenerated" not in text


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


def test_receipt_overwrite_refuses_conflicting_content(tmp_path):
    jobs = tmp_path / "jobs"
    resp = tmp_path / "resp"
    resp.mkdir()
    prepare_worker_jobs(dest=jobs)
    (resp / "job-repo-only-0.txt").write_text("print('v1')\n")
    first = write_receipt(resp, jobs, "job-repo-only-0")
    first_text = first.read_text()
    # Re-issuing an identical receipt is idempotent.
    assert write_receipt(resp, jobs, "job-repo-only-0").read_text() == first_text
    # A changed response must not silently replace the receipt.
    (resp / "job-repo-only-0.txt").write_text("print('v2')\n")
    try:
        write_receipt(resp, jobs, "job-repo-only-0")
    except ReceiptConflictError:
        pass
    else:
        raise AssertionError("expected ReceiptConflictError")
    assert first.read_text() == first_text


def test_receipt_metadata_mismatch_detected(tmp_path):
    jobs = tmp_path / "jobs"
    resp = tmp_path / "resp"
    resp.mkdir()
    prepare_worker_jobs(dest=jobs)
    (resp / "job-repo-only-0.txt").write_text("print('worker')\n")
    write_receipt(resp, jobs, "job-repo-only-0")
    receipt_path = resp / "job-repo-only-0.receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["model"] = "Some Other Model"
    receipt_path.write_text(json.dumps(receipt))
    assert (
        verify_receipt(resp, jobs, "job-repo-only-0", "repo-only", 0)
        == "receipt_metadata_mismatch"
    )


def test_receipt_failure_forces_run_failure(tmp_path, capsys):
    """A run whose receipt cannot be verified must not count as a pass,
    even when the response itself would score perfectly."""
    from run import ROOT  # noqa: E402

    jobs = tmp_path / "jobs"
    resp = tmp_path / "resp"
    resp.mkdir()
    prepare_worker_jobs(dest=jobs)
    # Use the known-good reference patch as the response so the only
    # failure is the missing receipt.
    ref = (ROOT / "variants" / "reference-worker.py").read_text()
    for c in CONDITIONS:
        for r in range(RUNS_PER_CONDITION):
            (resp / f"job-{c}-{r}.txt").write_text(ref)
    # Issue receipts for all but one run.
    for c in CONDITIONS:
        for r in range(RUNS_PER_CONDITION):
            if not (c == "repo-only" and r == 0):
                write_receipt(resp, jobs, f"job-{c}-{r}")
    rc = score_worker_responses(
        jobs_dir=jobs, resp_dir=resp, tag="test", out_dir=tmp_path
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "RECEIPT_RECEIPT_MISSING -> fail" in out
    reports = list(tmp_path.glob("worker-test-*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    bad = next(
        r for r in report["runs"]
        if r["condition"] == "repo-only" and r["run"] == 0
    )
    assert bad["receipt"] == "receipt_missing"
    assert bad["rubric_pass"] is False
    assert all(v is False for v in bad["rubric"].values())


def test_malformed_job_recorded_not_raised(tmp_path):
    jobs = tmp_path / "jobs"
    prepare_worker_jobs(dest=jobs)
    bad = jobs / "job-repo-only-0.json"
    job = json.loads(bad.read_text())
    job["context_items"] = "not-a-list-of-pairs"
    bad.write_text(json.dumps(job))
    result, note = load_job_for_scoring(jobs, "job-repo-only-0", "repo-only", 0)
    assert result is None
    assert note.startswith("job_malformed")


def test_delivered_context_violation_scores_invalid(tmp_path):
    """A job whose delivered context violates the protocol -- missing
    shared documents or leaked withheld identifiers -- is not a valid
    trial input, even when its hashes verify."""
    jobs = tmp_path / "jobs"
    prepare_worker_jobs(dest=jobs)
    # Memory arm without the shared corpus documents.
    bad = jobs / "job-repo-memory-0.json"
    job = json.loads(bad.read_text())
    job["supplemental_uris"] = ["ea:EA-002", "ea:EA-006"]
    job["context_items"] = [c for c in job["context_items"] if c[0].startswith("ea:")]
    job["prompt"] = worker_job_prompt(job["context_items"])
    job["prompt_sha256"] = hashlib.sha256(job["prompt"].encode()).hexdigest()
    bad.write_text(json.dumps(job))
    result, note = load_job_for_scoring(jobs, "job-repo-memory-0", "repo-memory", 0)
    assert result is None
    assert note == "job_context_violation: supplemental_uris"


def test_withheld_identifier_in_prompt_scores_invalid(tmp_path):
    jobs = tmp_path / "jobs"
    prepare_worker_jobs(dest=jobs)
    bad = jobs / "job-repo-memory-1.json"
    job = json.loads(bad.read_text())
    job["prompt"] = job["prompt"] + "\nIncident INC-412 background.\n"
    job["prompt_sha256"] = hashlib.sha256(job["prompt"].encode()).hexdigest()
    # context_items unchanged so the rebuilt prompt won't match; patch it
    # to keep hashes consistent and isolate the identifier check.
    job["context_items"].append(["ea:leak", "Incident INC-412 background."])
    job["prompt"] = worker_job_prompt(job["context_items"])
    job["prompt_sha256"] = hashlib.sha256(job["prompt"].encode()).hexdigest()
    bad.write_text(json.dumps(job))
    result, note = load_job_for_scoring(jobs, "job-repo-memory-1", "repo-memory", 1)
    assert result is None
    assert note == "job_context_violation: withheld_identifier"


def test_posthoc_receipt_excluded_from_capture_time_outcomes(tmp_path, capsys):
    """A valid posthoc receipt is preserved as evidence but its run does
    not qualify as a capture-time outcome."""
    from run import ROOT  # noqa: E402

    jobs = tmp_path / "jobs"
    resp = tmp_path / "resp"
    resp.mkdir()
    prepare_worker_jobs(dest=jobs)
    ref = (ROOT / "variants" / "reference-worker.py").read_text()
    (resp / "job-repo-only-0.txt").write_text(ref)
    write_receipt(resp, jobs, "job-repo-only-0", posthoc=True)
    assert (
        verify_receipt(resp, jobs, "job-repo-only-0", "repo-only", 0)
        == "receipt_posthoc"
    )
    rc = score_worker_responses(
        jobs_dir=jobs, resp_dir=resp, tag="test", out_dir=tmp_path
    )
    assert rc == 0
    report = json.loads(next(tmp_path.glob("worker-test-*.json")).read_text())
    row = next(
        r for r in report["runs"]
        if r["condition"] == "repo-only" and r["run"] == 0
    )
    assert row["receipt"] == "receipt_posthoc"
    assert row["rubric_pass"] is False
    assert any("excluded from capture-time" in n for n in row["notes"])
    # The other eight runs have no responses; they fail on missing
    # receipts, not on posthoc exclusion.
    assert sum(1 for r in report["runs"] if r["receipt"] == "receipt_posthoc") == 1


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
