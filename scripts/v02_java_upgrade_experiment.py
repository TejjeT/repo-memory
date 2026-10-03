"""v0.2 thin experiment: Java 17 -> 25 upgrade task.

Compares two context pipelines for the same engineering task:

  baseline:    repo doc chunks -> keyword retrieval ("plain repo RAG" stand-in)
  repo-memory: ContextAssembler — deterministic assertions first (scope,
               authorization, lifecycle), then supporting evidence

Measurement is a checklist of must-have facts per task. The repo-memory path
is asserted (it is the deterministic product claim); the baseline is reported
for comparison. This is the positioning experiment from issue #15: it measures
the value of the trusted layers, not the vector search.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from repo_memory.context import (
    ContextAssembler,
    ContextRequest,
    Evidence,
    EvidenceProvider,
    RepositoryMetadata,
    describe,
)
from repo_memory.loader import load_assertion
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.policy import ResolutionContext

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "examples" / "payments"
SCHEMA = ROOT / "spec" / "engineering-assertion.schema.json"
NOW = datetime(2026, 10, 3, tzinfo=UTC)
SOURCE = (Provenance(type="document", uri="test://v02-experiment"),)

# Synthetic corpus: generic upgrade docs that do NOT contain the authoritative
# constraints. Stands in for "repo chunks" in the baseline pipeline.
CORPUS = {
    "docs/java-25-upgrade-runbook.md": (
        "Java 25 upgrade runbook: update maven.compiler release to 25, run the "
        "full test suite, check deprecated APIs, roll out per service. Most "
        "services upgrade without issues."
    ),
    "docs/adr-0042-jvm-tuning.md": (
        "ADR-0042: JVM tuning for Java 25. G1GC remains the default; ZGC is "
        "available for low-latency services. No action required for the upgrade."
    ),
    "docs/legacy-settlement-readme.md": (
        "legacy-settlement runs on Java 17. An upgrade to a newer LTS is planned "
        "eventually when the team has capacity."
    ),
}


def keyword_retrieve(task: str, top_k: int = 3) -> list[str]:
    """Naive keyword retrieval standing in for plain repo vector search."""
    words = {w.strip(".,->").lower() for w in task.split() if len(w) > 2}
    scored = []
    for uri, text in CORPUS.items():
        tokens = {w.strip(".,").lower() for w in text.split()}
        scored.append((len(words & tokens), uri))
    scored.sort(reverse=True)
    return [CORPUS[uri] for _, uri in scored[:top_k]]


class CorpusEvidenceProvider(EvidenceProvider):
    """Fake semantic-evidence provider over the synthetic corpus."""

    def collect(self, request: ContextRequest) -> tuple[Evidence, ...]:
        return tuple(
            Evidence(
                uri=uri,
                kind="doc",
                snippet=text[:120],
                relates_to=("EA-001", "EA-003"),
                score=0.5,
                provenance=SOURCE,
            )
            for uri, text in CORPUS.items()
        )


@dataclass(frozen=True)
class Task:
    name: str
    task: str
    repository: str
    system: str | None
    must_have: tuple[str, ...]
    must_not_apply: tuple[str, ...]


TASKS = (
    Task(
        name="upgrade payment-api",
        task="upgrade Java 17 to 25 in payment-api",
        repository="payment-api",
        system=None,
        must_have=("target Java 25",),
        must_not_apply=("EA-003",),
    ),
    Task(
        name="upgrade legacy-settlement",
        task="upgrade Java 17 to 25 in legacy-settlement",
        repository="legacy-settlement",
        system="Settlement Platform",
        must_have=("remains on Java 17", "M-2027-01"),
        must_not_apply=("EA-001",),  # suppressed by EA-003's override
    ),
)


def check_facts(text: str, facts: tuple[str, ...]) -> dict[str, bool]:
    lowered = text.lower()
    return {fact: fact.lower() in lowered for fact in facts}


def main() -> int:
    assertions: tuple[EngineeringAssertion, ...] = tuple(
        load_assertion(path, SCHEMA) for path in sorted(FIXTURES.glob("*.json"))
    )
    assembler = ContextAssembler(providers=(CorpusEvidenceProvider(),))
    failures: list[str] = []

    for task in TASKS:
        print(f"=== {task.name}: {task.task} ===")
        request = ContextRequest(
            task=task.task,
            resolution=ResolutionContext(
                scope=Scope(
                    organization="Acme",
                    domain="Payments",
                    system=task.system,
                    repository=task.repository,
                ),
                when=NOW,
            ),
            repository=RepositoryMetadata(name=task.repository, language="java"),
        )

        # Baseline: plain repo RAG stand-in.
        baseline_text = "\n".join(keyword_retrieve(task.task))
        # Repo-memory path: deterministic assertions + supporting evidence.
        context = assembler.assemble(assertions, request)
        memory_text = "\n".join(
            [a.content for a in context.assertions]
            + [e.snippet for e in context.evidence]
        )
        memory_ids = [a.id for a in context.assertions]

        print(f"  repo-memory assertions: {memory_ids}")
        for fact, present in check_facts(memory_text, task.must_have).items():
            status = "ok" if present else "MISSING"
            print(f"  [repo-memory] must-have '{fact}': {status}")
            if not present:
                failures.append(f"{task.name}: repo-memory missing '{fact}'")
        for assertion_id in task.must_not_apply:
            applied = assertion_id in memory_ids
            status = "LEAKED" if applied else "ok"
            print(f"  [repo-memory] {assertion_id} not applicable: {status}")
            if applied:
                failures.append(f"{task.name}: {assertion_id} wrongly applied")

        for fact, present in check_facts(baseline_text, task.must_have).items():
            print(f"  [baseline] must-have '{fact}': {'ok' if present else 'missing'}")

        print(f"  assembled: {describe(context)['assertions']}")
        print()

    if failures:
        print("FAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("repo-memory path passed all checks on both tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
