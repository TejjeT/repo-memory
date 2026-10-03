"""First reproducible agent evaluation (#5): does repo-memory improve an
engineering decision?

Task: "Upgrade legacy-settlement from Java 17 to Java 25."

Conditions (model, task, and execution budget fixed across all three):

  repo-only:         code + repository documentation only
  generic-retrieval: repository + keyword retrieval over the policies corpus
                     (the exception document IS included -- otherwise we would
                     measure missing information, not structured memory)
  repo-memory:       same permitted source information via Engineering
                     Assertions + ContextAssembler, with the permission hooks
                     wired explicitly (no incident sources reach the agent)

The agent is a fixed deterministic decision procedure (simulated-agent-v1),
identical across conditions, so outcome differences come from the context,
not the agent. Nine runs (3 per condition, seeded) are a sanity check, not
proof of general superiority; failures are reported alongside successes.

Recorded per run: answer/patch, retrieved context, estimated tokens, and
policy violations. Rubric: (R1) recognized the active exception, (R2)
avoided the unauthorized upgrade, (R3) cited only permitted evidence.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))

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

ROOT = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FIXTURES = ROOT / "fixtures" / "legacy-settlement"
POLICIES = ROOT / "policies"
EA_FIXTURES = REPO_ROOT / "examples" / "payments"
SCHEMA = REPO_ROOT / "spec" / "engineering-assertion.schema.json"

TASK = "Upgrade legacy-settlement from Java 17 to Java 25."
REPO = "legacy-settlement"
MODEL = "simulated-agent-v1"
TOP_K = 5
NOW = datetime(2026, 10, 3, tzinfo=UTC)

# The simulated caller is an external agent with no incident access.
# Permission hooks are wired explicitly BEFORE any context is assembled.
allow_assertion = lambda a: True  # noqa: E731
allow_provenance = lambda p: p.type != "incident"  # noqa: E731
allow_evidence = lambda e: not e.uri.startswith("incident://")  # noqa: E731


def fixture_revision() -> str:
    digest = hashlib.sha256()
    for path in sorted(FIXTURES.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(FIXTURES).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def repo_files() -> dict[str, str]:
    return {
        str(p.relative_to(FIXTURES)): p.read_text()
        for p in sorted(FIXTURES.rglob("*"))
        if p.is_file()
    }


def policy_docs() -> dict[str, str]:
    return {
        f"policies/{p.name}": p.read_text()
        for p in sorted(POLICIES.glob("*.md"))
    }


def keyword_retrieve(task: str, docs: dict[str, str], top_k: int, seed: int) -> list[str]:
    """Deterministic keyword retrieval; ties broken by (seed, uri)."""
    words = {w.strip(".,->").lower() for w in task.split() if len(w) > 2}
    scored = []
    for uri, text in docs.items():
        tokens = {w.strip(".,").lower() for w in text.split()}
        overlap = len(words & tokens)
        tie = int(hashlib.sha256(f"{seed}:{uri}".encode()).hexdigest(), 16)
        scored.append((-overlap, tie, uri))
    scored.sort()
    return [uri for _, _, uri in scored[:top_k]]


@dataclass(frozen=True)
class AgentAnswer:
    decision: str  # HOLD | PROCEED | ABSTAIN
    rationale: list[str]
    citations: list[str]
    patch: str | None


def simulated_agent(task_repo: str, context: list[tuple[str, str]]) -> AgentAnswer:
    """Fixed decision procedure v1, identical across conditions.

    Reads (uri, text) context items: holds when a repo-specific version pin
    is present, proceeds on an org mandate otherwise, abstains when neither
    is found. Citations are the URIs of the items the decision rested on.
    """
    text = "\n".join(t for _, t in context).lower()
    pin = f"{task_repo} remains on java 17" in text or (
        task_repo in text and "remains on java 17" in text
    )
    mandate = "must target java 25" in text
    if pin:
        cited = [u for u, t in context if "remains on java 17" in t.lower()]
        return AgentAnswer(
            decision="HOLD",
            rationale=[
                f"Active exception pins {task_repo} to Java 17 "
                "(retirement milestone M-2027-01)."
            ],
            citations=cited,
            patch=None,
        )
    if mandate:
        return AgentAnswer(
            decision="PROCEED",
            rationale=["Enterprise policy mandates Java 25 for this scope."],
            citations=[u for u, t in context if "must target java 25" in t.lower()],
            patch=(
                "--- pom.xml\n+++ pom.xml\n"
                "-  <maven.compiler.release>17</maven.compiler.release>\n"
                "+  <maven.compiler.release>25</maven.compiler.release>"
            ),
        )
    return AgentAnswer(
        decision="ABSTAIN",
        rationale=["No applicable policy found in context."],
        citations=[],
        patch=None,
    )


def score_rubric(answer: AgentAnswer) -> dict[str, bool]:
    rationale = " ".join(answer.rationale).lower()
    return {
        "R1_recognized_exception": "m-2027-01" in rationale or "remains on java 17" in rationale,
        "R2_avoided_unauthorized_upgrade": answer.decision == "HOLD" and answer.patch is None,
        "R3_permitted_evidence_only": all(
            not c.startswith("incident://") for c in answer.citations
        ),
    }


def policy_violations(answer: AgentAnswer) -> list[str]:
    violations = []
    if any(c.startswith("incident://") for c in answer.citations):
        violations.append("cited_restricted_source")
    if answer.decision == "PROCEED":
        violations.append("unauthorized_upgrade")
    return violations


class PolicyEvidenceProvider(EvidenceProvider):
    """Evidence provider over the permitted policy documents."""

    def __init__(self, docs: dict[str, str]) -> None:
        self.docs = docs

    def collect(
        self, request: ContextRequest, candidates: tuple[EngineeringAssertion, ...]
    ) -> tuple[Evidence, ...]:
        ids = {a.id for a in candidates}
        link = {
            "policies/java-runtime-policy.md": ("EA-001",),
            "policies/legacy-settlement-exception.md": ("EA-003",),
        }
        items: list[Evidence] = []
        for uri, text in self.docs.items():
            relates = tuple(aid for aid in link.get(uri, ()) if aid in ids)
            items.append(
                Evidence(
                    uri=uri,
                    kind="doc",
                    snippet=text[:160],
                    relates_to=relates,
                    score=0.5,
                    provenance=(Provenance(type="document", uri=uri),),
                )
            )
        # One restricted incident-sourced item: the hooks must keep it out.
        items.append(
            Evidence(
                uri="incident://inc-2024-118",
                kind="incident",
                snippet="ledger client undefined behavior on newer runtimes",
                relates_to=("EA-003",) if "EA-003" in ids else (),
                score=0.9,
                provenance=(Provenance(type="incident", uri="incident://inc-2024-118"),),
            )
        )
        return tuple(items)


def build_repo_memory_context(seed: int) -> tuple[list[tuple[str, str]], dict]:
    assertions: list[EngineeringAssertion] = [
        load_assertion(p, SCHEMA) for p in sorted(EA_FIXTURES.glob("*.json"))
    ]
    # Scenario setup (fixtures stay pristine): the exception's provenance
    # includes a restricted incident entry, exercising the hooks.
    assertions = [
        replace(
            a,
            provenance=a.provenance
            + (Provenance(type="incident", uri="incident://inc-2024-118"),),
        )
        if a.id == "EA-003"
        else a
        for a in assertions
    ]
    request = ContextRequest(
        task=TASK,
        resolution=ResolutionContext(
            scope=Scope(
                organization="Acme",
                domain="Payments",
                system="Settlement Platform",
                repository=REPO,
            ),
            when=NOW,
        ),
        repository=RepositoryMetadata(name=REPO, language="java", build_tool="maven"),
        evidence_budget=TOP_K,
    )
    assembler = ContextAssembler(
        providers=(PolicyEvidenceProvider(policy_docs()),),
        authorize=allow_assertion,
        authorize_evidence=allow_evidence,
        authorize_provenance=allow_provenance,
    )
    context = assembler.assemble(tuple(assertions), request)
    items = [(f"ea:{a.id}", a.content) for a in context.assertions]
    items += [(e.uri, e.snippet) for e in context.evidence]
    return items, describe(context)


def build_condition(condition: str, seed: int) -> list[tuple[str, str]]:
    files = repo_files()
    if condition == "repo-only":
        return list(files.items())
    if condition == "generic-retrieval":
        docs = {**files, **policy_docs()}
        uris = keyword_retrieve(TASK, docs, TOP_K, seed)
        return [(u, docs[u]) for u in uris]
    if condition == "repo-memory":
        items, _ = build_repo_memory_context(seed)
        return items
    raise ValueError(condition)


def estimate_tokens(*texts: str) -> int:
    return sum(len(t) // 4 for t in texts)


def main() -> int:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True,
            cwd=Path(__file__).resolve().parent.parent.parent,
        ).strip()
    except Exception:
        commit = "unknown"
    report: dict = {
        "experiment": "agent-eval-01",
        "task": TASK,
        "model": MODEL,
        "budget": {"top_k": TOP_K, "evidence_budget": TOP_K},
        "fixture_revision": fixture_revision(),
        "repo_commit": commit,
        "conditions": ["repo-only", "generic-retrieval", "repo-memory"],
        "runs_per_condition": 3,
        "runs": [],
    }
    for condition in report["conditions"]:
        for run in range(3):
            seed = run
            context = build_condition(condition, seed)
            answer = simulated_agent(REPO, context)
            rubric = score_rubric(answer)
            violations = policy_violations(answer)
            context_text = "\n".join(t for _, t in context)
            answer_text = "\n".join(answer.rationale) + (answer.patch or "")
            report["runs"].append(
                {
                    "condition": condition,
                    "run": run,
                    "seed": seed,
                    "answer": asdict(answer),
                    "retrieved_uris": [u for u, _ in context],
                    "tokens_estimated": estimate_tokens(context_text, answer_text),
                    "rubric": rubric,
                    "rubric_pass": all(rubric.values()),
                    "policy_violations": violations,
                }
            )
            marks = "".join("✓" if v else "✗" for v in rubric.values())
            print(f"{condition:17s} run {run}: {answer.decision:7s} [{marks}] "
                  f"violations={violations or 'none'}")

    summary: dict[str, dict[str, int]] = {}
    for r in report["runs"]:
        s = summary.setdefault(r["condition"], {"pass": 0, "total": 0})
        s["total"] += 1
        s["pass"] += r["rubric_pass"]
    print()
    for condition, s in summary.items():
        print(f"{condition:17s}: {s['pass']}/{s['total']} runs passed rubric")
    report["summary"] = summary

    out = ROOT / "runs" / f"run-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nrecorded: {out.relative_to(ROOT.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
