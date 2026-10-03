"""Unit tests for the agent-eval harness components (not the experiment).

Covers the review findings on PR #17: equal repository context across
conditions, grounded (non-invented) agent claims, permission measured on
delivered context, and a replayable input manifest.
"""

import importlib.util
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
