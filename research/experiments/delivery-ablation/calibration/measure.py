"""Measure real supersession rates from public decision corpora.

Inputs are local copies fetched by the operator; nothing is downloaded here.

    python measure.py --peps <python/peps checkout>/peps \
        --rfc-index rfc-index.xml --adr-dataset <ADR-Study-Dataset>/repositories

Prints one JSON document. See README.md for sources, revisions and limits.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

NS = {"r": "https://www.rfc-editor.org/rfc-index"}


def _chain_lengths(successor_of: dict[str, set[str]], heads: set[str]) -> Counter[int]:
    """Count revisions on the longest path ending at each current head."""

    predecessors: dict[str, set[str]] = {}
    for old, news in successor_of.items():
        for new in news:
            predecessors.setdefault(new, set()).add(old)

    def depth(node: str, seen: frozenset[str]) -> int:
        below = [p for p in predecessors.get(node, ()) if p not in seen]
        return 1 + max((depth(p, seen | {node}) for p in below), default=0)

    return Counter(depth(h, frozenset()) for h in heads)


def measure_peps(directory: Path) -> dict:
    headers: dict[str, dict[str, str]] = {}
    for path in sorted(directory.glob("pep-*.rst")):
        fields: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                break
            match = re.match(r"^([A-Za-z-]+):\s*(.*)$", line)
            if match:
                fields[match.group(1).lower()] = match.group(2).strip()
        if "pep" in fields:
            headers[str(int(fields["pep"]))] = fields

    def refs(value: str | None) -> set[str]:
        return {str(int(n)) for n in re.findall(r"\d+", value or "")}

    replaces = {pep: refs(h.get("replaces")) for pep, h in headers.items()}
    superseded_by = {pep: refs(h.get("superseded-by")) for pep, h in headers.items()}
    status = {pep: h.get("status", "") for pep, h in headers.items()}

    # Every (old, new) pair asserted from either side.
    pairs = {(old, new) for new, olds in replaces.items() for old in olds if old in headers}
    pairs |= {(old, new) for old, news in superseded_by.items() for new in news if new in headers}
    replaced = {old for old, _ in pairs}
    successor_of: dict[str, set[str]] = {}
    for old, new in pairs:
        successor_of.setdefault(old, set()).add(new)
    heads = {new for _, new in pairs} - replaced

    adopted = {"Final", "Active", "Accepted", "Provisional", "Superseded"}
    return {
        "documents": len(headers),
        "adopted_or_superseded": sum(s in adopted for s in status.values()),
        "status_superseded": sum(s == "Superseded" for s in status.values()),
        "replaced_by_any_link": len(replaced),
        "replacement_pairs": len(pairs),
        "pairs_linked_from_both_sides": sum(
            old in replaces.get(new, ()) and new in superseded_by.get(old, ()) for old, new in pairs
        ),
        "pairs_only_successor_says_replaces": sum(
            old in replaces.get(new, ()) and new not in superseded_by.get(old, ())
            for old, new in pairs
        ),
        "pairs_only_predecessor_says_superseded_by": sum(
            old not in replaces.get(new, ()) and new in superseded_by.get(old, ())
            for old, new in pairs
        ),
        "replaced_but_status_not_superseded": sorted(
            (old, status[old]) for old in replaced if status[old] != "Superseded"
        ),
        "status_superseded_without_link": sorted(
            pep for pep, s in status.items() if s == "Superseded" and pep not in replaced
        ),
        "chain_lengths": dict(sorted(_chain_lengths(successor_of, heads).items())),
    }


def measure_rfcs(index: Path) -> dict:
    root = ET.parse(index).getroot()
    status: dict[str, str] = {}
    obsoleted_by: dict[str, set[str]] = {}
    obsoletes: dict[str, set[str]] = {}
    for entry in root.findall("r:rfc-entry", NS):
        doc = entry.findtext("r:doc-id", namespaces=NS)
        status[doc] = entry.findtext("r:current-status", default="", namespaces=NS)
        for tag, table in (("obsoleted-by", obsoleted_by), ("obsoletes", obsoletes)):
            node = entry.find(f"r:{tag}", NS)
            if node is not None:
                ids = {d.text for d in node.findall("r:doc-id", NS)}
                table[doc] = {i for i in ids if i and i.startswith("RFC")}

    published = {d for d, s in status.items() if s != "NOT ISSUED"}
    pairs = {(old, new) for old, news in obsoleted_by.items() for new in news}
    pairs |= {(old, new) for new, olds in obsoletes.items() for old in olds}
    pairs = {(o, n) for o, n in pairs if o in published and n in published}
    replaced = {old for old, _ in pairs}
    successor_of: dict[str, set[str]] = {}
    for old, new in pairs:
        successor_of.setdefault(old, set()).add(new)
    heads = {new for _, new in pairs} - replaced
    return {
        "documents": len(published),
        "obsoleted": len(replaced),
        "replacement_pairs": len(pairs),
        "pairs_linked_from_both_sides": sum(
            old in obsoletes.get(new, ()) and new in obsoleted_by.get(old, ()) for old, new in pairs
        ),
        "obsoleted_current_status": dict(Counter(status[o] for o in replaced).most_common()),
        "chain_lengths": dict(sorted(_chain_lengths(successor_of, heads).items())),
    }


def measure_adr_dataset(directory: Path) -> dict:
    statuses: Counter[str] = Counter()
    repositories = files = 0
    for path in sorted(directory.glob("*.json")):
        repositories += 1
        for adr in json.loads(path.read_text(encoding="utf-8")).get("adrFiles") or []:
            files += 1
            raw = (adr.get("status") or "").strip().lower()
            word = re.match(r"[a-z]+", raw)
            statuses[word.group(0) if word else "(none)"] += 1
    return {
        "repositories": repositories,
        "adr_files": files,
        "status_first_word": dict(statuses.most_common(12)),
        "status_superseded_any_spelling": sum(
            n for word, n in statuses.items() if re.match(r"super[sc]ed", word)
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peps", type=Path)
    parser.add_argument("--rfc-index", type=Path)
    parser.add_argument("--adr-dataset", type=Path)
    args = parser.parse_args()
    out = {}
    if args.peps:
        out["peps"] = measure_peps(args.peps)
    if args.rfc_index:
        out["rfcs"] = measure_rfcs(args.rfc_index)
    if args.adr_dataset:
        out["adr_dataset"] = measure_adr_dataset(args.adr_dataset)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
