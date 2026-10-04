"""First reproducible agent evaluation (#5): does repo-memory improve an
engineering decision?

Task: "Upgrade legacy-settlement from Java 17 to Java 25."

Conditions (model, task, and execution budget fixed across all three):

  repo-only:         repository files only (the same four files every arm
                     receives), no supplemental material
  generic-retrieval: repository files + keyword retrieval over the policies
                     corpus (the exception document IS included -- otherwise
                     we would measure missing information, not structure)
  repo-memory:       repository files + Engineering Assertions + evidence via
                     ContextAssembler, with the permission hooks wired
                     explicitly (no incident sources reach the agent)

Every arm receives the identical repository context; supplemental material
is retrieved separately under a comparable budget (TOP_K supplemental
items per arm) and recorded. The agent is a fixed deterministic decision
procedure (simulated-agent-v2), identical across conditions, so outcome
differences come from the context, not the agent. v2 grounds every claim:
it only holds when a repository-specific pin is present in the evidence
it actually received, and it extracts the milestone from that evidence
rather than having it injected. Abstaining is scored as *not* recognizing
the exception (safe, but unsolved). Nine runs (3 per condition, seeded)
are a sanity check, not proof of general superiority; failures are
reported alongside successes.

Recorded per run: answer/patch, delivered context (repo + supplemental),
estimated tokens, a replayable input manifest (content hashes of every
effective input), and policy violations. Rubric: (R1) recognized the active
exception (grounded in cited evidence), (R2) avoided the unauthorized
upgrade, (R3) cited only permitted evidence. Permission is measured on the
*delivered* context, not just the citations.

This is a harness dry run with a deterministic simulator, not the measured
coding-agent experiment requested in #5/#15: three seeds on one deterministic
actor are not three independent agent trials. A real-agent execution path
is the next slice.
"""

from __future__ import annotations

import hashlib
import json
import re
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
MODEL = "simulated-agent-v2"
TOP_K = 5  # supplemental-item budget, applied identically to both retrieval arms
SUPPLEMENTAL_BUDGET = TOP_K
NOW = datetime(2026, 10, 3, tzinfo=UTC)

MILESTONE_RE = re.compile(r"M-\d{4}-\d{2}")
PIN_PHRASE = "remains on java 17"
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"[a-z0-9-]+")

# The simulated caller is an external agent with no incident access.
# Permission hooks are wired explicitly BEFORE any context is assembled.
allow_assertion = lambda a: True  # noqa: E731
allow_provenance = lambda p: p.type != "incident"  # noqa: E731
allow_evidence = lambda e: not e.uri.startswith("incident://")  # noqa: E731


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


def extract_grounded_pin(
    task_repo: str, context: list[tuple[str, str]]
) -> tuple[str, str] | None:
    """Bind repository, pin, and milestone to one explicit statement.

    A pin grounds only when, within a single sentence, the repository name
    appears as the pin's subject (within the 3 words preceding "remains on
    Java 17") and a retirement milestone follows the pin before the next pin
    or the sentence ends. A document that merely co-mentions another
    repository -- even in an adjacent sentence, or earlier in the same
    sentence -- never grounds a pin.

    This is a narrow documented parser for the synthetic scaffold, not a
    general NLP claim: it handles singular-subject statements of the form
    "<repo> remains on Java 17 until <milestone>". Constructions that
    genuinely entangle two repositories' pins in one clause remain
    ambiguous and are out of scope.
    """
    repo = task_repo.lower()
    for uri, text in context:
        for sentence in SENTENCE_SPLIT.split(text):
            low = sentence.lower()
            pins = list(re.finditer(PIN_PHRASE, low))
            for i, pin in enumerate(pins):
                before = WORD_RE.findall(low[: pin.start()])
                if repo not in before[-3:]:
                    continue
                window_end = pins[i + 1].start() if i + 1 < len(pins) else len(sentence)
                match = MILESTONE_RE.search(sentence, pin.end(), window_end)
                if match:
                    return uri, match.group(0)
    return None


def simulated_agent(task_repo: str, context: list[tuple[str, str]]) -> AgentAnswer:
    """Fixed decision procedure v2, identical across conditions.

    Reads (uri, text) context items: holds only when a pin for the target
    repository is grounded in the evidence it received (milestone extracted
    from that evidence); proceeds on an org mandate otherwise; abstains when
    neither is found. Citations are the URIs of the items the decision
    rested on.
    """
    grounded = extract_grounded_pin(task_repo, context)
    if grounded:
        uri, milestone = grounded
        return AgentAnswer(
            decision="HOLD",
            rationale=[
                f"Active exception pins {task_repo} to Java 17 "
                f"until retirement milestone {milestone}."
            ],
            citations=[uri],
            patch=None,
        )
    mandate = [u for u, t in context if "must target java 25" in t.lower()]
    if mandate:
        return AgentAnswer(
            decision="PROCEED",
            rationale=["Enterprise policy mandates Java 25 for this scope."],
            citations=mandate,
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


def score_rubric(
    answer: AgentAnswer, task_repo: str, context: list[tuple[str, str]]
) -> dict[str, bool]:
    """R1 requires a *grounded* exception: the cited evidence must name the
    target repository, pin it to Java 17, and contain the milestone the answer
    states. ABSTAIN is safe but unsolved, so it fails R1 while passing R2."""
    grounded = extract_grounded_pin(task_repo, context)
    milestone_ok = False
    if grounded and answer.decision == "HOLD":
        uri, milestone = grounded
        milestone_ok = uri in answer.citations and milestone in " ".join(
            answer.rationale
        )
    return {
        "R1_recognized_exception": milestone_ok,
        "R2_avoided_unauthorized_upgrade": answer.decision != "PROCEED",
        "R3_permitted_evidence_only": all(
            not c.startswith("incident://") for c in answer.citations
        ),
    }


def policy_violations(
    answer: AgentAnswer, delivered_uris: list[str], permitted_uris: set[str]
) -> list[str]:
    """Permission is measured on the *delivered* agent input, not just what
    the agent chose to cite: restricted context reaching the agent is a
    violation even when it goes uncited."""
    violations = []
    leaked = sorted(u for u in delivered_uris if u not in permitted_uris)
    if leaked:
        violations.append(f"restricted_context_delivered:{','.join(leaked)}")
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


def build_repo_memory_supplemental(seed: int) -> tuple[list[tuple[str, str]], dict]:
    """Supplemental repo-memory context only; repo files are added by the
    caller so every arm receives identical repository context."""
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
    return items[:SUPPLEMENTAL_BUDGET], describe(context)


def build_condition(
    condition: str, seed: int
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (repo_items, supplemental_items). The repo items are identical
    for every condition; only the supplemental retrieval path differs, under
    a comparable TOP_K-item budget."""
    repo_items = list(repo_files().items())
    if condition == "repo-only":
        return repo_items, []
    if condition == "generic-retrieval":
        docs = policy_docs()
        uris = keyword_retrieve(TASK, docs, TOP_K, seed)
        return repo_items, [(u, docs[u]) for u in uris]
    if condition == "repo-memory":
        supplemental, _ = build_repo_memory_supplemental(seed)
        return repo_items, supplemental
    raise ValueError(condition)


def permitted_uris(condition: str, repo_uris: list[str], supplemental_uris: list[str]) -> set[str]:
    """The explicit permitted-source policy, applied identically to both
    retrieval arms: repository files are always permitted; supplemental
    URIs are permitted only when they passed the condition's own retrieval
    path. Incident-sourced URIs are never permitted."""
    allowed = set(repo_uris)
    if condition == "generic-retrieval":
        allowed |= {u for u in supplemental_uris if u.startswith("policies/")}
    elif condition == "repo-memory":
        allowed |= {
            u
            for u in supplemental_uris
            if u.startswith("ea:") or u.startswith("policies/")
        }
    return allowed


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_manifest() -> dict:
    """Content hashes of every effective input, so a recorded run is
    replayable: fixture files, policy corpus, runner, assertion fixtures,
    the imported core package, and the schema -- plus the git state they
    were read from."""
    files = [p for p in sorted(FIXTURES.rglob("*")) if p.is_file()]
    files += [p for p in sorted(POLICIES.glob("*.md")) if p.is_file()]
    files += [p for p in sorted(EA_FIXTURES.glob("*.json")) if p.is_file()]
    files += [p for p in sorted((REPO_ROOT / "src" / "repo_memory").glob("*.py"))]
    files += [SCHEMA, Path(__file__).resolve()]
    hashes = {
        str(p.relative_to(REPO_ROOT)): sha256_file(p) for p in files
    }
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=REPO_ROOT
        ).strip()
        porcelain = subprocess.check_output(
            ["git", "status", "--porcelain"], text=True, cwd=REPO_ROOT
        )
        # The sample output directory is not an effective input (its
        # contents are never hashed), so it does not dirty the manifest.
        dirty = any(
            "research/experiments/agent-eval/runs/" not in line
            for line in porcelain.splitlines()
            if line.strip()
        )
    except Exception:
        commit, dirty = "unknown", None
    return {
        "input_hashes": hashes,
        "git_commit": commit,
        "git_dirty": dirty,
        "runner": {
            "model": MODEL,
            "task": TASK,
            "repository": REPO,
            "supplemental_budget": SUPPLEMENTAL_BUDGET,
            "seeds": [0, 1, 2],
        },
    }


def estimate_tokens(*texts: str) -> int:
    return sum(len(t) // 4 for t in texts)


def main() -> int:
    manifest = input_manifest()
    report: dict = {
        "experiment": "agent-eval-01",
        "task": TASK,
        "model": MODEL,
        "manifest": manifest,
        "conditions": ["repo-only", "generic-retrieval", "repo-memory"],
        "runs_per_condition": 3,
        "runs": [],
    }
    for condition in report["conditions"]:
        for run in range(3):
            seed = run
            repo_items, supplemental_items = build_condition(condition, seed)
            context = repo_items + supplemental_items
            answer = simulated_agent(REPO, context)
            rubric = score_rubric(answer, REPO, context)
            delivered_uris = [u for u, _ in context]
            permitted = permitted_uris(
                condition,
                [u for u, _ in repo_items],
                [u for u, _ in supplemental_items],
            )
            violations = policy_violations(answer, delivered_uris, permitted)
            repo_text = "\n".join(t for _, t in repo_items)
            supp_text = "\n".join(t for _, t in supplemental_items)
            answer_text = "\n".join(answer.rationale) + (answer.patch or "")
            # A run is successful only when the answer is right AND nothing
            # restricted reached the agent: detected permission failures fail
            # the run and the summary, even when the answer scores well.
            passed = all(rubric.values()) and not violations
            report["runs"].append(
                {
                    "condition": condition,
                    "run": run,
                    "seed": seed,
                    "answer": asdict(answer),
                    "repo_uris": [u for u, _ in repo_items],
                    "supplemental_uris": [u for u, _ in supplemental_items],
                    "supplemental_text": {
                        u: t for u, t in supplemental_items
                    },
                    "tokens_estimated": {
                        "repo": estimate_tokens(repo_text),
                        "supplemental": estimate_tokens(supp_text),
                        "answer": estimate_tokens(answer_text),
                    },
                    "rubric": rubric,
                    "policy_violations": violations,
                    "rubric_pass": passed,
                }
            )
            marks = "".join("✓" if v else "✗" for v in rubric.values())
            flag = " VIOLATIONS" if violations else ""
            print(f"{condition:17s} run {run}: {answer.decision:7s} [{marks}]"
                  f"{flag} violations={violations or 'none'}")

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
    print(f"manifest: {len(manifest['input_hashes'])} inputs hashed, "
          f"commit={manifest['git_commit'][:12]}, dirty={manifest['git_dirty']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
