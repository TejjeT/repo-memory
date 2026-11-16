"""Agreement script and label template for the #8 labelling study."""

import csv
import importlib.util
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1] / "research/memory-worthiness"


@pytest.fixture(scope="module")
def agreement():
    spec = importlib.util.spec_from_file_location("agreement", BASE / "labels/agreement.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, labels):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["candidate_id", "label"])
        writer.writerows(labels.items())
    return path


def test_template_lists_every_candidate_once_and_is_unlabelled():
    rows = list(csv.DictReader((BASE / "labels/TEMPLATE.csv").open()))
    ids = [row["candidate_id"] for row in rows]
    expected = {f"RM-C{i}" for i in range(1, 7)} | {f"RM-E{i}" for i in range(1, 15)}
    assert set(ids) == expected and len(ids) == 20
    assert all(row["label"] == "" and row["reviewer"] == "" for row in rows)
    text = (BASE / "candidates.md").read_text() + (BASE / "candidates-external.md").read_text()
    assert all(f"## {cid}:" in text for cid in expected)


def test_reviewer_facing_files_carry_no_proposed_labels():
    external = (BASE / "candidates-external.md").read_text()
    assert "do-not-keep" not in external
    internal = (BASE / "candidates.md").read_text()
    assert "*do-not-keep*" not in internal and "*keep*" not in internal


def test_kappa_values(agreement):
    a = {"1": "keep", "2": "keep", "3": "do-not-keep", "4": "do-not-keep"}
    assert agreement.cohen_kappa(a, a) == (1.0, 1.0)
    b = {"1": "keep", "2": "do-not-keep", "3": "keep", "4": "do-not-keep"}
    assert agreement.cohen_kappa(a, b) == (0.5, 0.0)
    same = {"1": "keep", "2": "keep"}
    assert agreement.cohen_kappa(same, same) == (1.0, None)


def test_incomplete_or_mismatched_labels_are_refused(agreement, tmp_path):
    with pytest.raises(ValueError):
        agreement.read_labels(write(tmp_path / "r1.csv", {"RM-C1": ""}))
    with pytest.raises(ValueError):
        agreement.cohen_kappa({"1": "keep"}, {"2": "keep"})


def test_single_reviewer_reports_nothing(agreement, tmp_path, capsys):
    path = write(tmp_path / "r1.csv", {"RM-C1": "keep"})
    assert agreement.main([str(path)]) == 2
    assert "at least two" in capsys.readouterr().err
