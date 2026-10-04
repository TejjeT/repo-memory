"""Unit tests for the agent-eval harness components (not the experiment).

Covers the review findings on PR #17: equal repository context across
conditions, grounded (non-invented) agent claims, permission measured on
delivered context, and a replayable input manifest.
"""

import importlib.util
import json
from pathlib import Path

RUN_PY = (
    Path(__file__).resolve().parent.parent
    / "research"
    / "experiments"
    / "agent-eval"
    / "run.py"
)


def load_run():
    import sys

    spec = importlib.util.spec_from_file_location("agent_eval_run", RUN_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_eval_run"] = module
    spec.loader.exec_module(module)
    return module


run = load_run()


def test_keyword_retrieve_is_deterministic():
    docs = {"a": "java upgrade guide", "b": "java upgrade guide"}
    first = run.keyword_retrieve("upgrade java", docs, top_k=2, seed=0)
    second = run.keyword_retrieve("upgrade java", docs, top_k=2, seed=0)
    assert first == second
    assert len(first) == 2


def test_keyword_retrieve_respects_top_k():
    docs = {f"d{i}": "java" for i in range(10)}
    assert len(run.keyword_retrieve("java", docs, top_k=3, seed=1)) == 3


def test_all_conditions_receive_identical_repo_context():
    """Finding 1: the base repository context must not vary by condition."""
    repo_uris = None
    for condition in ("repo-only", "generic-retrieval", "repo-memory"):
        repo_items, _supplemental = run.build_condition(condition, seed=0)
        uris = [u for u, _ in repo_items]
        assert len(uris) == 4, f"{condition} repo context changed"
        if repo_uris is None:
            repo_uris = uris
        assert uris == repo_uris, f"{condition} repo context differs"
    assert repo_uris == sorted(repo_uris)


def test_supplemental_budget_is_bounded():
    for condition in ("generic-retrieval", "repo-memory"):
        _repo, supplemental = run.build_condition(condition, seed=0)
        assert len(supplemental) <= run.SUPPLEMENTAL_BUDGET


def test_simulated_agent_grounds_milestone_from_evidence():
    """Finding 2: the milestone must come from the evidence, not the actor."""
    context = [
        ("policies/exception.md", "legacy-settlement remains on Java 17 until M-2031-06")
    ]
    answer = run.simulated_agent("legacy-settlement", context)
    assert answer.decision == "HOLD"
    assert answer.patch is None
    assert "M-2031-06" in " ".join(answer.rationale)
    assert "M-2027-01" not in " ".join(answer.rationale)
    assert answer.citations == ["policies/exception.md"]


def test_simulated_agent_ignores_other_service_exception():
    """Finding 2: another service's exception must not pin this repository."""
    context = [
        ("README.md", "legacy-settlement service"),
        ("policies/other.md", "other-service remains on Java 17 until M-2030-02"),
    ]
    answer = run.simulated_agent("legacy-settlement", context)
    assert answer.decision == "ABSTAIN"
    assert "M-2030-02" not in " ".join(answer.rationale)


def test_same_document_co_mention_does_not_ground_pin():
    """Repro from re-review: both repositories in one document, pin belongs
    to the other service -- the target repository must not hold."""
    context = [
        (
            "policies/multi.md",
            "legacy-settlement should upgrade to Java 25. "
            "other-service remains on Java 17 until M-2030-02.",
        )
    ]
    assert run.extract_grounded_pin("legacy-settlement", context) is None
    answer = run.simulated_agent("legacy-settlement", context)
    assert answer.decision == "ABSTAIN"  # no grounded pin, no mandate phrasing
    rubric = run.score_rubric(answer, "legacy-settlement", context)
    assert not rubric["R1_recognized_exception"]


def test_pin_binding_requires_subject_before_pin():
    """A bare co-mention earlier in the same sentence is not a subject."""
    context = [
        (
            "policies/multi.md",
            "Notes on legacy-settlement and the fleet: other-service remains "
            "on Java 17 until M-2031-04.",
        )
    ]
    assert run.extract_grounded_pin("legacy-settlement", context) is None


def test_contrast_clause_does_not_ground_pin():
    """Repro from re-review: an unambiguous single-sentence contrast must
    not create a false exception for the target repository."""
    context = [
        (
            "policies/multi.md",
            "Unlike legacy-settlement, other-service remains on Java 17 "
            "until M-2030-02.",
        )
    ]
    assert run.extract_grounded_pin("legacy-settlement", context) is None
    assert run.extract_grounded_pin("other-service", context) == (
        "policies/multi.md",
        "M-2030-02",
    )
    answer = run.simulated_agent("legacy-settlement", context)
    assert answer.decision == "ABSTAIN"
    rubric = run.score_rubric(answer, "legacy-settlement", context)
    assert not rubric["R1_recognized_exception"]


def test_two_repos_each_bind_their_own_milestone():
    """A document with separate valid pins binds each milestone correctly."""
    context = [
        (
            "policies/multi.md",
            "legacy-settlement remains on Java 17 until M-2027-01. "
            "other-service remains on Java 17 until M-2030-02.",
        )
    ]
    assert run.extract_grounded_pin("legacy-settlement", context) == (
        "policies/multi.md",
        "M-2027-01",
    )
    assert run.extract_grounded_pin("other-service", context) == (
        "policies/multi.md",
        "M-2030-02",
    )


def test_repo_token_boundaries():
    """The repo name must be a standalone token, not part of a longer one."""
    context = [
        ("policies/multi.md", "my-legacy-settlement remains on Java 17 until M-2031-04.")
    ]
    assert run.extract_grounded_pin("legacy-settlement", context) is None
    assert run.extract_grounded_pin("my-legacy-settlement", context) == (
        "policies/multi.md",
        "M-2031-04",
    )


def test_pin_binds_repo_subject_and_following_milestone():
    context = [
        (
            "ea:EA-003",
            "legacy-settlement remains on Java 17 until retirement milestone "
            "M-2027-01. Do not upgrade before then.",
        )
    ]
    assert run.extract_grounded_pin("legacy-settlement", context) == (
        "ea:EA-003",
        "M-2027-01",
    )


def test_violations_fail_the_run_and_summary():
    """Repro from re-review: a deliberately broken evidence hook (allow-all)
    delivers the planted incident item; the run must fail even though the
    answer scores well."""
    repo_items = list(run.repo_files().items())
    supplemental, _describe = run.build_repo_memory_supplemental(
        0, hook_overrides={"authorize_evidence": lambda e: True}
    )
    context = repo_items + supplemental
    delivered = [u for u, _ in context]
    assert "incident://inc-2024-118" in delivered
    permitted = run.permitted_uris(
        "repo-memory",
        [u for u, _ in repo_items],
        [u for u, _ in supplemental],
    )
    answer = run.simulated_agent("legacy-settlement", context)
    rubric = run.score_rubric(answer, "legacy-settlement", context)
    violations = run.policy_violations(answer, delivered, permitted)
    assert any(v.startswith("restricted_context_delivered") for v in violations)
    # The headline gate: violations fail the run regardless of rubric.
    assert not (all(rubric.values()) and not violations)


def test_simulated_agent_proceeds_on_mandate():
    context = [("policies/runtime.md", "New Java services must target Java 25.")]
    answer = run.simulated_agent("payment-api", context)
    assert answer.decision == "PROCEED"
    assert answer.patch is not None and "25" in answer.patch


def test_abstain_fails_recognition_but_passes_no_upgrade():
    """Finding 2: safe abstention is not exception recognition."""
    context = [("README.md", "a service")]
    answer = run.simulated_agent("legacy-settlement", context)
    assert answer.decision == "ABSTAIN"
    rubric = run.score_rubric(answer, "legacy-settlement", context)
    assert not rubric["R1_recognized_exception"]
    assert rubric["R2_avoided_unauthorized_upgrade"]
    assert rubric["R3_permitted_evidence_only"]


def test_rubric_requires_grounded_citation():
    held = run.AgentAnswer(
        decision="HOLD",
        rationale=["Active exception pins legacy-settlement to Java 17 until M-2027-01."],
        citations=["ea:EA-003"],
        patch=None,
    )
    context = [("ea:EA-003", "legacy-settlement remains on Java 17 until M-2027-01.")]
    assert all(run.score_rubric(held, "legacy-settlement", context).values())

    # Same answer, but the citation does not ground the claim.
    ungrounded = run.AgentAnswer(
        decision="HOLD",
        rationale=["Active exception pins legacy-settlement to Java 17 until M-2027-01."],
        citations=["policies/other.md"],
        patch=None,
    )
    other = [("policies/other.md", "other-service remains on Java 17 until M-2030-02")]
    rubric = run.score_rubric(ungrounded, "legacy-settlement", other)
    assert not rubric["R1_recognized_exception"]


def test_delivered_restricted_context_is_a_violation_even_uncited():
    """Finding 3: permission is measured on delivered context, not citations."""
    answer = run.AgentAnswer(
        decision="HOLD",
        rationale=["Active exception pins legacy-settlement to Java 17 until M-2027-01."],
        citations=["ea:EA-003"],
        patch=None,
    )
    context = [
        ("ea:EA-003", "legacy-settlement remains on Java 17 until M-2027-01."),
        ("incident://inc-2024-118", "ledger client undefined behavior"),
    ]
    delivered = [u for u, _ in context]
    permitted = run.permitted_uris("repo-memory", [], ["ea:EA-003"])
    violations = run.policy_violations(answer, delivered, permitted)
    assert any(v.startswith("restricted_context_delivered") for v in violations)
    assert "incident://inc-2024-118" in violations[0]


def test_permitted_source_policy_is_explicit_and_shared():
    repo = ["pom.xml", "README.md"]
    supp = ["policies/exception.md", "incident://inc-1"]
    for condition in ("generic-retrieval", "repo-memory"):
        permitted = run.permitted_uris(condition, repo, supp)
        assert "pom.xml" in permitted
        assert "incident://inc-1" not in permitted
    assert run.permitted_uris("repo-only", repo, supp) == set(repo)


def test_repo_memory_supplemental_never_delivers_incident_evidence():
    """The planted incident:// evidence must not reach the agent input."""
    _repo, supplemental = run.build_condition("repo-memory", seed=0)
    uris = [u for u, _ in supplemental]
    assert not any(u.startswith("incident://") for u in uris)
    assert any(u == "ea:EA-003" for u in uris)


def test_exception_doc_contains_no_restricted_identifiers():
    """Finding 3: the permitted exception summary must not leak incident ids."""
    text = (run.POLICIES / "legacy-settlement-exception.md").read_text()
    assert "INC-" not in text
    assert "incident://" not in text
    assert "legacy-settlement remains on Java 17" in text


def test_input_manifest_hashes_every_effective_input():
    """Finding 4: the recorded run must identify all inputs by content hash."""
    manifest = run.input_manifest()
    hashes = manifest["input_hashes"]
    assert len(hashes) >= 20
    rels = set(hashes)
    assert any(r.startswith("research/experiments/agent-eval/fixtures/") for r in rels)
    assert any(r.startswith("research/experiments/agent-eval/policies/") for r in rels)
    assert any(r.startswith("examples/payments/") and r.endswith(".json") for r in rels)
    assert "spec/engineering-assertion.schema.json" in rels
    assert "research/experiments/agent-eval/run.py" in rels
    assert manifest["runner"]["model"] == "simulated-agent-v2"
    assert manifest["git_commit"] not in ("unknown", "")
    assert manifest["git_dirty"] in (True, False)


def test_policy_violations_flagged():
    bad = run.AgentAnswer(
        decision="PROCEED",
        rationale=["upgrade now"],
        citations=["incident://inc-1"],
        patch="diff",
    )
    violations = run.policy_violations(bad, ["incident://inc-1"], set())
    assert "cited_restricted_source" in violations
    assert "unauthorized_upgrade" in violations
    assert any(v.startswith("restricted_context_delivered") for v in violations)

    good = run.AgentAnswer(
        decision="HOLD",
        rationale=["Active exception pins legacy-settlement to Java 17 until M-2027-01."],
        citations=["ea:EA-003"],
        patch=None,
    )
    assert run.policy_violations(good, ["ea:EA-003"], {"ea:EA-003"}) == []


def test_parse_worker_response_valid():
    raw = (
        "DECISION: HOLD\n"
        "RATIONALE: Exception pins legacy-settlement to Java 17 until M-2027-01.\n"
        "CITATIONS: ea:EA-003\n"
        "PATCH:\n"
        "NONE\n"
    )
    answer = run.parse_worker_response(raw)
    assert answer is not None
    assert answer.decision == "HOLD"
    assert answer.citations == ["ea:EA-003"]
    assert answer.patch is None


def test_parse_worker_response_with_patch():
    raw = (
        "DECISION: PROCEED\n"
        "RATIONALE: Mandate applies.\n"
        "CITATIONS: policies/java-runtime-policy.md\n"
        "PATCH:\n"
        "--- pom.xml\n+++ pom.xml\n-  <maven.compiler.release>17</maven.compiler.release>\n"
        "+  <maven.compiler.release>25</maven.compiler.release>\n"
    )
    answer = run.parse_worker_response(raw)
    assert answer is not None
    assert answer.decision == "PROCEED"
    assert answer.patch is not None and "25" in answer.patch


def test_parse_worker_response_rejects_bad_format():
    assert run.parse_worker_response("looks good, hold the upgrade") is None
    assert (
        run.parse_worker_response(
            "DECISION: MAYBE\nRATIONALE: x\nCITATIONS: NONE\nPATCH:\nNONE\n"
        )
        is None
    )
    assert run.parse_worker_response("") is None


def test_prepare_worker_jobs(tmp_path):
    import json

    paths = run.prepare_worker_jobs(dest=tmp_path)
    assert len(paths) == 9
    repo_uris = None
    for name in paths:
        job = json.loads((tmp_path / name).read_text())
        assert job["task"] == run.TASK
        assert job["repository"] == run.REPO
        assert "TARGET REPOSITORY: legacy-settlement" in job["prompt"]
        assert job["prompt"].count("RULES (follow exactly):") == 1
        if repo_uris is None:
            repo_uris = job["repo_uris"]
        assert job["repo_uris"] == repo_uris
    # every job carries the replayable manifest
    assert len(job["manifest"]["input_hashes"]) >= 30


def test_hold_with_patch_fails():
    """A HOLD decision that ships an upgrade patch is an invalid response."""
    context = [("ea:EA-003", "legacy-settlement remains on Java 17 until M-2027-01.")]
    answer = run.AgentAnswer(
        decision="HOLD",
        rationale=["pins legacy-settlement to Java 17 until M-2027-01."],
        citations=["ea:EA-003"],
        patch="--- pom.xml\n+<maven.compiler.release>25</maven.compiler.release>",
    )
    rubric = run.score_rubric(answer, "legacy-settlement", context)
    assert not rubric["R2_avoided_unauthorized_upgrade"]
    violations = run.policy_violations(answer, ["ea:EA-003"], {"ea:EA-003"})
    assert "patch_without_proceed" in violations


def test_fabricated_citation_fails():
    """Citations to sources the agent never received are invalid."""
    context = [("ea:EA-003", "legacy-settlement remains on Java 17 until M-2027-01.")]
    answer = run.AgentAnswer(
        decision="HOLD",
        rationale=["pins legacy-settlement to Java 17 until M-2027-01."],
        citations=["policies/made-up.md"],
        patch=None,
    )
    rubric = run.score_rubric(answer, "legacy-settlement", context)
    assert not rubric["R3_permitted_evidence_only"]
    violations = run.policy_violations(answer, ["ea:EA-003"], {"ea:EA-003"})
    assert any(v.startswith("fabricated_citation") for v in violations)


def test_parse_requires_patch_label_and_rationale():
    assert (
        run.parse_worker_response(
            "DECISION: HOLD\nRATIONALE: exception holds.\nCITATIONS: ea:EA-003\n"
        )
        is None
    )
    assert (
        run.parse_worker_response(
            "DECISION: HOLD\nRATIONALE:   \nCITATIONS: ea:EA-003\nPATCH:\nNONE\n"
        )
        is None
    )
    # PATCH: present with empty value parses as no patch.
    answer = run.parse_worker_response(
        "DECISION: HOLD\nRATIONALE: exception holds.\nCITATIONS: ea:EA-003\nPATCH:"
    )
    assert answer is not None and answer.patch is None


def test_parse_rejects_duplicate_fields():
    dup_decision = (
        "DECISION: HOLD\n"
        "RATIONALE: exception holds.\n"
        "DECISION: PROCEED\n"
        "CITATIONS: ea:EA-003\n"
        "PATCH:\n"
        "NONE\n"
    )
    assert run.parse_worker_response(dup_decision) is None
    dup_rationale = (
        "DECISION: HOLD\n"
        "RATIONALE: exception holds.\n"
        "RATIONALE: actually it does not.\n"
        "CITATIONS: ea:EA-003\n"
        "PATCH:\n"
        "NONE\n"
    )
    assert run.parse_worker_response(dup_rationale) is None
    dup_patch = (
        "DECISION: HOLD\n"
        "RATIONALE: exception holds.\n"
        "CITATIONS: ea:EA-003\n"
        "PATCH:\n"
        "--- pom.xml\n"
        "PATCH:\n"
        "+++ pom.xml\n"
    )
    # A second PATCH: line falls inside the patch body, so this parses --
    # but the body is then a real patch and fails R2 for HOLD.
    answer = run.parse_worker_response(dup_patch)
    assert answer is not None and answer.patch is not None
    rubric = run.score_rubric(answer, "legacy-settlement", [("ea:EA-003", "x")])
    assert not rubric["R2_avoided_unauthorized_upgrade"]


def test_parse_preserves_inline_patch_content():
    raw = (
        "DECISION: HOLD\n"
        "RATIONALE: exception holds.\n"
        "CITATIONS: ea:EA-003\n"
        "PATCH: --- pom.xml\n+++ pom.xml\n"
    )
    answer = run.parse_worker_response(raw)
    assert answer is not None
    assert answer.patch is not None and "pom.xml" in answer.patch
    rubric = run.score_rubric(answer, "legacy-settlement", [("ea:EA-003", "x")])
    assert not rubric["R2_avoided_unauthorized_upgrade"]


def test_parse_inline_patch_none_is_no_patch():
    raw = (
        "DECISION: HOLD\n"
        "RATIONALE: exception holds.\n"
        "CITATIONS: ea:EA-003\n"
        "PATCH: NONE"
    )
    answer = run.parse_worker_response(raw)
    assert answer is not None and answer.patch is None


def test_load_job_validates_prompt_binding(tmp_path):
    run.prepare_worker_jobs(dest=tmp_path / "jobs")
    job, note = run.load_job_for_scoring(
        tmp_path / "jobs", "job-repo-memory-0"
    )
    assert note == "ok" and job is not None

    # Tampered prompt: hash mismatch -> inconsistent.
    tampered = tmp_path / "jobs" / "job-repo-memory-0.json"
    data = json.loads(tampered.read_text())
    data["prompt"] = "No exception evidence was delivered."
    tampered.write_text(json.dumps(data))
    _, note = run.load_job_for_scoring(tmp_path / "jobs", "job-repo-memory-0")
    assert note == "job_inconsistent"

    # Dropped URIs: context/URI disagreement -> inconsistent.
    data = json.loads(
        (tmp_path / "jobs" / "job-repo-memory-1.json").read_text()
    )
    data["supplemental_uris"] = []
    (tmp_path / "jobs" / "job-repo-memory-1.json").write_text(
        json.dumps(data)
    )
    _, note = run.load_job_for_scoring(tmp_path / "jobs", "job-repo-memory-1")
    assert note == "job_inconsistent"


def test_load_job_missing_and_corrupt(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    _, note = run.load_job_for_scoring(jobs, "job-repo-memory-0")
    assert note == "job_missing"
    (jobs / "job-repo-memory-0.json").write_text("{not json")
    _, note = run.load_job_for_scoring(jobs, "job-repo-memory-0")
    assert note == "job_corrupt"
    (jobs / "job-repo-memory-0.json").write_text(json.dumps({"a": 1}))
    _, note = run.load_job_for_scoring(jobs, "job-repo-memory-0")
    assert note == "job_corrupt"


def test_scoring_survives_bad_jobs(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    resp = tmp_path / "resp"
    resp.mkdir()
    (tmp_path / "runs").mkdir()
    run.prepare_worker_jobs(dest=jobs)
    # Remove one job, corrupt another; scoring must record failed runs,
    # not abort the batch.
    (jobs / "job-repo-only-0.json").unlink()
    (jobs / "job-generic-retrieval-1.json").write_text("garbage{")
    monkeypatch.setattr(run, "ROOT", tmp_path)
    rc = run.score_worker_responses(jobs, resp, tag="test-bad-jobs")
    assert rc == 0
    reports = list((tmp_path / "runs").glob("test-bad-jobs-*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    notes = {
        (r["condition"], r["run"]): r["notes"] for r in report["runs"]
    }
    assert notes[("repo-only", 0)] == ["job_missing"]
    assert notes[("generic-retrieval", 1)] == ["job_corrupt"]
    assert all(not r["rubric_pass"] for r in report["runs"]
               if r["notes"] in (["job_missing"], ["job_corrupt"]))


def test_worker_metadata_recorded(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    resp = tmp_path / "resp"
    resp.mkdir()
    (tmp_path / "runs").mkdir()
    run.prepare_worker_jobs(dest=jobs)
    monkeypatch.setattr(run, "ROOT", tmp_path)
    run.score_worker_responses(jobs, resp, tag="test-meta")
    report = json.loads(next((tmp_path / "runs").glob("test-meta-*.json")).read_text())
    assert report["model"] == "Muse Spark"
    assert report["worker"]["turns_per_run"] == 1
    assert len(report["worker"]["brief_sha256"]) == 64
    assert "unknown" in report["worker"]["sampling_params"]
