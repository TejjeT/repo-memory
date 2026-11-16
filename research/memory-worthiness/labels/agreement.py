"""Agreement between reviewers' label files (issue #8).

    python research/memory-worthiness/labels/agreement.py labels/r1.csv labels/r2.csv

Reads the ``label`` column of each CSV. Reports raw agreement and Cohen's
kappa for each pair of reviewers, and lists every disagreement. It refuses
incomplete or unknown labels instead of guessing.
"""

from __future__ import annotations

import csv
import itertools
import sys
from collections import Counter
from pathlib import Path

LABELS = ("keep", "do-not-keep", "uncertain")


def read_labels(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    labels = {row["candidate_id"]: row["label"].strip().lower() for row in rows}
    bad = {cid: label for cid, label in labels.items() if label not in LABELS}
    if bad:
        raise ValueError(f"{path}: missing or unknown labels for {sorted(bad)}")
    return labels


def cohen_kappa(first: dict[str, str], second: dict[str, str]) -> tuple[float, float | None]:
    """Return (raw agreement, kappa). Kappa is None when chance agreement is 1."""

    if first.keys() != second.keys():
        raise ValueError("reviewers labelled different candidate sets")
    n = len(first)
    observed = sum(first[c] == second[c] for c in first) / n
    a, b = Counter(first.values()), Counter(second.values())
    expected = sum(a[label] * b[label] for label in LABELS) / (n * n)
    return observed, None if expected == 1 else (observed - expected) / (1 - expected)


def main(paths: list[str]) -> int:
    if len(paths) < 2:
        print("Agreement needs at least two reviewers' files.", file=sys.stderr)
        return 2
    reviewers = {Path(p).stem: read_labels(Path(p)) for p in paths}
    for (name_a, a), (name_b, b) in itertools.combinations(reviewers.items(), 2):
        observed, kappa = cohen_kappa(a, b)
        shown = "undefined (both used one label throughout)" if kappa is None else f"{kappa:.2f}"
        print(f"{name_a} vs {name_b}: n={len(a)}, raw agreement {observed:.0%}, kappa {shown}")
        for candidate in sorted(a):
            if a[candidate] != b[candidate]:
                print(f"  {candidate}: {name_a}={a[candidate]}  {name_b}={b[candidate]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
