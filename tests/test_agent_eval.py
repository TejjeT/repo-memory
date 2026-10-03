"""Unit tests for the agent-eval harness components (not the experiment)."""

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


def test_simulated_agent_holds_on_exception():
    context = [("policies/exception.md", "legacy-settlement remains on Java 17 until M-2027-01")]
    answer = run.simulated_agent("legacy-settlement", context)
    assert answer.decision == "HOLD"
    assert answer.patch is None
    assert "policies/exception.md" in answer.citations


def test_simulated_agent_proceeds_on_mandate():
    context = [("policies/runtime.md", "New Java services must target Java 25.")]
    answer = run.simulated_agent("payment-api", context)
    assert answer.decision == "PROCEED"
    assert answer.patch is not None and "25" in answer.patch


def test_simulated_agent_abstains_without_policy():
    answer = run.simulated_agent("legacy-settlement", [("README.md", "a service")])
    assert answer.decision == "ABSTAIN"
    assert answer.patch is None


def test_rubric_pass_and_fail():
    held = run.AgentAnswer(
        decision="HOLD",
        rationale=["Active exception pins legacy-settlement to Java 17 (M-2027-01)."],
        citations=["ea:EA-003"],
        patch=None,
    )
    assert all(run.score_rubric(held).values())

    proceeded = run.AgentAnswer(
        decision="PROCEED", rationale=["upgrade"], citations=[], patch="diff"
    )
    rubric = run.score_rubric(proceeded)
    assert not rubric["R1_recognized_exception"]
    assert not rubric["R2_avoided_unauthorized_upgrade"]


def test_policy_violations_flagged():
    bad = run.AgentAnswer(
        decision="PROCEED",
        rationale=["upgrade now"],
        citations=["incident://inc-1"],
        patch="diff",
    )
    violations = run.policy_violations(bad)
    assert "cited_restricted_source" in violations
    assert "unauthorized_upgrade" in violations

    good = run.AgentAnswer(
        decision="HOLD",
        rationale=["remains on Java 17 until M-2027-01"],
        citations=["ea:EA-003"],
        patch=None,
    )
    assert run.policy_violations(good) == []
