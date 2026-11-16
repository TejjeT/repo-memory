"""Checks for the synthetic delivery ablation harness (no model involved)."""

import importlib.util
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "research/experiments/delivery-ablation/ablation.py"
SMALL = {"domains": 2, "systems_per_domain": 2, "queries": 150}


@pytest.fixture(scope="module")
def abl():
    spec = importlib.util.spec_from_file_location("delivery_ablation", PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def run(abl):
    world = abl.generate(abl.Config(seed=7, **SMALL))
    return world, abl.deliver(world, 50)


def test_generation_is_deterministic(abl):
    first = abl.generate(abl.Config(seed=3, **SMALL))
    assert first.digest() == abl.generate(abl.Config(seed=3, **SMALL)).digest()
    assert first.digest() != abl.generate(abl.Config(seed=4, **SMALL)).digest()


def test_ground_truth_does_not_come_from_the_engine(abl, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("generator must not call the policy engine")

    monkeypatch.setattr(abl, "resolve_assertions", fail)
    assert abl.generate(abl.Config(seed=1, **SMALL)).queries


def test_independent_filter_stack_matches_engine_without_relations(abl, run):
    _, delivered = run
    assert delivered["L4 +scope ancestry/targets"] == delivered["RM without relations"]


def test_authorization_first_systems_never_deliver_restricted(abl, run):
    world, delivered = run
    restricted = {d.assertion.id for d in world.docs if d.restricted}
    for name in abl.SYSTEMS[1:]:
        for query, got in zip(world.queries, delivered[name], strict=True):
            assert query.cleared or not set(got) & restricted, name


def test_engine_is_clean_outside_documented_gaps(abl, run):
    world, delivered = run
    topic_of = {d.assertion.id: d.topic for d in world.docs}
    gaps = {"governing-hidden", "broken-chain", "hidden-successor"}
    checked = 0
    for query, got in zip(world.queries, delivered["RM full (policy.py)"], strict=True):
        if query.tags & gaps:
            continue
        checked += 1
        assert abl.outcome(query, got, topic_of) == "clean", query
    assert checked > 100


def test_outcome_classification(abl):
    query = abl.Query(
        scope=abl.Scope(organization="acme"),
        topic="t",
        text="t",
        scoped_text="t",
        cleared=True,
        required=frozenset({"A"}),
        tags=frozenset(),
    )
    topic_of = {"A": "t", "B": "t", "C": "other"}
    assert abl.outcome(query, ["A", "C"], topic_of) == "clean"
    assert abl.outcome(query, ["A", "B"], topic_of) == "needs-resolution"
    assert abl.outcome(query, ["C"], topic_of) == "missed"
    assert abl.outcome(query, ["B"], topic_of) == "misleading"
