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
    Caller,
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

MILESTONE_RE = re.compile(r"M-\d{4}-\d{2}", re.IGNORECASE)


def pin_statement_re(task_repo: str) -> re.Pattern[str]:
    """Exact match for the documented synthetic statement grammar.

    ``<exact repo> remains on Java 17 until [retirement milestone] <M-YYYY-MM>``

    with token boundaries around the repository name and flexible
    whitespace. Anything that does not match this grammar is ungrounded --
    no proximity heuristics, no NLP.
    """
    repo = re.escape(task_repo)
    return re.compile(
        rf"(?<![\w-]){repo}(?![\w-])\s+remains\s+on\s+java\s+17\s+until\s+"
        rf"(?:retirement\s+milestone\s+)?(M-\d{{4}}-\d{{2}})",
        re.IGNORECASE,
    )

# The simulated caller is an external agent with no incident access.
# All three authorization hooks are bound to this one authenticated caller
# (issue #15); nothing here defaults to permissive behavior.
EVAL_CALLER = Caller(
    id="eval-external-agent",
    grants=(
        "catalog://",
        "github://",
        "architecture-exception://",
        "policy://",
        "policies/",
        "ea:",
    ),
)


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

    A pin grounds only when the evidence contains the documented synthetic
    statement grammar (see ``pin_statement_re``): the exact repository name
    as a standalone token, directly followed by the pin phrase and the
    milestone. A document that merely co-mentions another repository --
    even in a contrastive clause like "Unlike legacy-settlement,
    other-service remains ..." -- never grounds a pin for the target repo.
    Unsupported constructions are treated as ungrounded.

    This is a narrow documented parser for the synthetic scaffold, not a
    general NLP claim.
    """
    pattern = pin_statement_re(task_repo)
    for uri, text in context:
        match = pattern.search(text)
        if match:
            return uri, match.group(1)
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
    states. ABSTAIN is safe but unsolved, so it fails R1 while passing R2.
    R2 fails when the upgrade was performed OR when a patch is produced
    without a PROCEED decision. R3 fails on uncited-permission sources and
    on fabricated citations (URIs the agent never received)."""
    grounded = extract_grounded_pin(task_repo, context)
    milestone_ok = False
    if grounded and answer.decision == "HOLD":
        uri, milestone = grounded
        milestone_ok = uri in answer.citations and milestone in " ".join(
            answer.rationale
        )
    delivered = {u for u, _ in context}
    return {
        "R1_recognized_exception": milestone_ok,
        "R2_avoided_unauthorized_upgrade": answer.decision != "PROCEED"
        and answer.patch is None,
        "R3_permitted_evidence_only": all(
            not c.startswith("incident://") for c in answer.citations
        )
        and all(c in delivered for c in answer.citations),
    }


def policy_violations(
    answer: AgentAnswer, delivered_uris: list[str], permitted_uris: set[str]
) -> list[str]:
    """Permission is measured on the *delivered* agent input, not just what
    the agent chose to cite: restricted context reaching the agent is a
    violation even when it goes uncited. Invalid agent outputs are also
    violations: a patch without a PROCEED decision, and citations to
    sources the agent never received."""
    violations = []
    leaked = sorted(u for u in delivered_uris if u not in permitted_uris)
    if leaked:
        violations.append(f"restricted_context_delivered:{','.join(leaked)}")
    if any(c.startswith("incident://") for c in answer.citations):
        violations.append("cited_restricted_source")
    fabricated = sorted(c for c in answer.citations if c not in delivered_uris)
    if fabricated:
        violations.append(f"fabricated_citation:{','.join(fabricated)}")
    if answer.patch and answer.decision != "PROCEED":
        violations.append("patch_without_proceed")
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


def build_repo_memory_supplemental(
    seed: int,
    caller: Caller = EVAL_CALLER,
    hook_overrides: dict | None = None,
) -> tuple[list[tuple[str, str]], dict]:
    """Supplemental repo-memory context only; repo files are added by the
    caller so every arm receives identical repository context. Authorization
    hooks are bound to one authenticated caller (issue #15); hook_overrides
    may replace individual hooks, e.g. to fault-inject a broken binding."""
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
    assembler = ContextAssembler.for_caller(
        caller,
        providers=(PolicyEvidenceProvider(policy_docs()),),
        **(hook_overrides or {}),
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


# ---------------------------------------------------------------------------
# Real-agent runner (issue #5, next slice)
#
# The simulator above is the fast harness regression path. The worker runner
# below is the interchangeable real-agent path: it consumes the *exact*
# prepared context (same build_condition, same permission hooks) and records
# raw responses, while outcome scoring stays mechanical and independent of
# the agent.
#
# Flow:
#   1. python run.py prepare-workers   -> writes runs/worker-jobs/*.json
#   2. one worker trial per job file, fixed prompt, single response
#   3. raw responses saved to runs/worker-responses/<job>.txt
#   4. python run.py score-workers     -> mechanical scoring -> report JSON
#
# Blinded trials: the orchestrating conversation must contain no experiment
# history (e.g. a fresh side chat). Responses go to
# runs/worker-responses-blind/<job>.txt and are scored with
#   python run.py score-workers-blind -> worker-blind-<stamp>.json
# ---------------------------------------------------------------------------

WORKER_MODEL = "subagent-worker-v1"
WORKER_TURNS = 1  # single response, no tool use

WORKER_PROMPT = """\
You are an engineer deciding whether to upgrade a repository's Java version.

TASK: {task}
TARGET REPOSITORY: {repository}

You receive CONTEXT as numbered items. Each item starts with its source URI
in brackets, e.g. [policies/example.md].

RULES (follow exactly):
- Respond exactly once, in one message. Do not use any tools.
- Decide HOLD (do not upgrade), PROCEED (upgrade), or ABSTAIN (not enough
  information to decide safely).
- HOLD only if the context contains an explicit statement of the form
  "<repository> remains on Java 17 until <M-YYYY-MM>" for the TARGET
  repository named above. A statement about any other repository does not
  count, no matter how similar it looks.
- PROCEED only if the context mandates Java 25 for the target repository
  and no exception above blocks it.
- Otherwise ABSTAIN.

OUTPUT FORMAT (exact labels, one per line):
DECISION: <HOLD | PROCEED | ABSTAIN>
RATIONALE: <one or two sentences>
CITATIONS: <comma-separated source URIs from the context you relied on, or NONE>
PATCH:
<unified diff changing maven.compiler.release in pom.xml, or the single word NONE>

CONTEXT:
{context}\
"""


def worker_job_prompt(task: str, repository: str, context: list[tuple[str, str]]) -> str:
    numbered = "\n\n".join(f"[{u}]\n{t}" for u, t in context)
    return WORKER_PROMPT.format(task=task, repository=repository, context=numbered)


def prepare_worker_jobs(dest: Path | None = None) -> list[str]:
    """Write one job file per condition x seed with the exact prepared context."""
    jobs_dir = dest if dest else ROOT / "runs" / "worker-jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    manifest = input_manifest()
    paths = []
    for condition in ("repo-only", "generic-retrieval", "repo-memory"):
        for seed in range(3):
            repo_items, supplemental_items = build_condition(condition, seed)
            context_items = repo_items + supplemental_items
            job = {
                "condition": condition,
                "seed": seed,
                "task": TASK,
                "repository": REPO,
                "prompt": worker_job_prompt(TASK, REPO, context_items),
                "repo_uris": [u for u, _ in repo_items],
                "supplemental_uris": [u for u, _ in supplemental_items],
                # The exact delivered context the worker received, as
                # [uri, text] pairs. Scoring reads this back; it never
                # rebuilds context, so the score always reflects what the
                # worker actually saw.
                "context_items": [[u, t] for u, t in context_items],
                "manifest": manifest,
            }
            path = jobs_dir / f"job-{condition}-{seed}.json"
            path.write_text(json.dumps(job, indent=2))
            paths.append(path.name)
    print(f"prepared {len(paths)} worker jobs in {jobs_dir}")
    return paths


def parse_worker_response(raw: str) -> AgentAnswer | None:
    """Mechanical parse of the fixed worker output format. None when the
    response does not follow the format -- recorded as a failed run. Every
    labeled field is required, including PATCH: (whose value may be NONE)."""
    decision = rationale = citations = None
    patch_seen = False
    in_patch = False
    patch_lines: list[str] = []
    for line in raw.splitlines():
        if in_patch:
            patch_lines.append(line)
            continue
        if line.startswith("DECISION:"):
            decision = line.split(":", 1)[1].strip().upper()
        elif line.startswith("RATIONALE:"):
            rationale = line.split(":", 1)[1].strip()
        elif line.startswith("CITATIONS:"):
            citations = line.split(":", 1)[1].strip()
        elif line.startswith("PATCH:"):
            patch_seen = True
            in_patch = True
    if decision not in ("HOLD", "PROCEED", "ABSTAIN"):
        return None
    if not rationale or citations is None or not patch_seen:
        return None
    cited = (
        []
        if citations.upper() == "NONE"
        else [c.strip() for c in citations.split(",") if c.strip()]
    )
    patch_text = "\n".join(patch_lines).strip()
    return AgentAnswer(
        decision=decision,
        rationale=[rationale],
        citations=cited,
        patch=None if patch_text.upper() == "NONE" or not patch_text else patch_text,
    )


def score_worker_responses(
    jobs_dir: Path | None = None,
    resp_dir: Path | None = None,
    tag: str = "worker",
) -> int:
    """Mechanically score recorded worker responses into a report.

    Scoring reads the saved job files (the exact context each worker
    received); it never rebuilds context."""
    jobs_dir = jobs_dir or ROOT / "runs" / "worker-jobs"
    resp_dir = resp_dir or ROOT / "runs" / "worker-responses"
    manifest = input_manifest()
    report: dict = {
        "experiment": "agent-eval-01",
        "task": TASK,
        "model": WORKER_MODEL,
        "agent": "worker",
        "turns_per_run": WORKER_TURNS,
        "manifest": manifest,
        "conditions": ["repo-only", "generic-retrieval", "repo-memory"],
        "runs_per_condition": 3,
        "blinded": "blind" in tag,
        "runs": [],
    }
    for condition in report["conditions"]:
        for seed in range(3):
            name = f"job-{condition}-{seed}"
            job = json.loads((jobs_dir / f"{name}.json").read_text())
            resp_path = resp_dir / f"{name}.txt"
            raw = resp_path.read_text() if resp_path.exists() else ""
            # Score what the worker actually received, as saved in the job --
            # never rebuild context here.
            context = [(u, t) for u, t in job["context_items"]]
            answer = parse_worker_response(raw) if raw else None
            if answer is None:
                rubric = {
                    "R1_recognized_exception": False,
                    "R2_avoided_unauthorized_upgrade": False,
                    "R3_permitted_evidence_only": False,
                }
                notes = ["response_unparseable"] if raw else ["response_missing"]
                answer_dict = None
            else:
                rubric = score_rubric(answer, REPO, context)
                notes = []
                answer_dict = asdict(answer)
            delivered_uris = [u for u, _ in context]
            permitted = permitted_uris(
                condition,
                job["repo_uris"],
                job["supplemental_uris"],
            )
            violations = (
                policy_violations(answer, delivered_uris, permitted)
                if answer
                else ["no_answer"]
            )
            passed = bool(answer) and all(rubric.values()) and not violations
            report["runs"].append(
                {
                    "condition": condition,
                    "run": seed,
                    "seed": seed,
                    "answer": answer_dict,
                    "raw_response": raw,
                    "repo_uris": job["repo_uris"],
                    "supplemental_uris": job["supplemental_uris"],
                    "tokens_estimated": {
                        "prompt": estimate_tokens(job["prompt"]),
                        "response": estimate_tokens(raw),
                    },
                    "turns": WORKER_TURNS,
                    "rubric": rubric,
                    "policy_violations": violations,
                    "notes": notes,
                    "rubric_pass": passed,
                }
            )
            marks = "".join("✓" if v else "✗" for v in rubric.values())
            flag = " VIOLATIONS" if violations else ""
            dec = answer.decision if answer else "NO_ANSWER"
            print(f"{condition:17s} run {seed}: {dec:9s} [{marks}]{flag} "
                  f"violations={violations or 'none'} notes={notes or 'none'}")

    summary: dict[str, dict[str, int]] = {}
    for r in report["runs"]:
        s = summary.setdefault(r["condition"], {"pass": 0, "total": 0})
        s["total"] += 1
        s["pass"] += r["rubric_pass"]
    print()
    for condition, s in summary.items():
        print(f"{condition:17s}: {s['pass']}/{s['total']} runs passed")
    report["summary"] = summary

    out = ROOT / "runs" / f"{tag}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nrecorded: {out.relative_to(ROOT.parent.parent)}")
    return 0


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
    if len(sys.argv) > 1 and sys.argv[1] == "prepare-workers":
        prepare_worker_jobs()
    elif len(sys.argv) > 1 and sys.argv[1] == "score-workers":
        raise SystemExit(score_worker_responses())
    elif len(sys.argv) > 1 and sys.argv[1] == "score-workers-blind":
        blind_jobs = ROOT / "runs" / "worker-jobs"
        blind_resp = ROOT / "runs" / "worker-responses-blind"
        raise SystemExit(
            score_worker_responses(blind_jobs, blind_resp, tag="worker-blind")
        )
    else:
        raise SystemExit(main())
