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
#
# Receipts bind each response to its exact job at collection time:
#   python run.py record-receipts [resp_dir] [--posthoc]
# Scoring verifies the receipt; a regenerated or swapped job breaks the
# linkage and fails the run. --posthoc backfills pre-receipt batches and
# labels the receipts issued_posthoc.
# ---------------------------------------------------------------------------

# Worker-trial execution metadata. The workers are subagents powered by the
# Muse model available in this environment; the exact version string and
# sampling parameters are not exposed by the runtime, so they are recorded
# as unknown rather than invented. WORKER_BRIEF is the canonical worker
# instruction text; its hash is recorded in every report so the brief is
# versioned alongside the results.
WORKER_MODEL = "Muse Spark"
WORKER_MODEL_DETAIL = "unknown (runtime does not expose a version string)"
WORKER_PROTOCOL = "subagent-worker-v1"  # runner label, not a model id
WORKER_TURNS = 1  # single response, no follow-up turns
WORKER_TOOL_POLICY = "read the assigned job file only; no browsing, no other tools"
WORKER_SAMPLING_PARAMS = "unknown (runtime defaults; not exposed)"
WORKER_BRIEF = (
    "You are participating in a controlled evaluation trial. "
    "Read the file at {job_path} and take its \"prompt\" field as your "
    "complete task: it contains the TASK, the CONTEXT, and the OUTPUT FORMAT. "
    "Rules: you may read ONLY that one file. Do not use any other tools, "
    "do not browse the web, do not read other files. Produce exactly ONE "
    "response message following the OUTPUT FORMAT in the prompt, then stop."
)

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
            prompt = worker_job_prompt(TASK, REPO, context_items)
            job = {
                "condition": condition,
                "seed": seed,
                "task": TASK,
                "repository": REPO,
                "prompt": prompt,
                # Binds the prompt to the job: scoring rejects any job
                # whose prompt was edited after preparation.
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
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
    labeled field is required exactly once, including PATCH: (whose value
    may be NONE). Strictness rules, all regressions from review:

    - a repeated DECISION:/RATIONALE:/CITATIONS:/PATCH: label is
      contradictory input, not an override -- reject
    - content on the PATCH: line itself is patch content, never silently
      discarded: an inline diff is scored as a patch, "NONE" as no patch
    - everything after the PATCH: line is patch body, including lines that
      look like labels
    - an empty patch payload is not valid: the documented format requires
      a unified diff or the single word NONE
    """
    seen: set[str] = set()
    decision = rationale = citations = None
    patch_lines: list[str] = []
    in_patch = False
    for line in raw.splitlines():
        if in_patch:
            patch_lines.append(line)
            continue
        for label in ("DECISION:", "RATIONALE:", "CITATIONS:", "PATCH:"):
            if line.startswith(label):
                if label in seen:
                    return None
                seen.add(label)
                value = line.split(":", 1)[1]
                if label == "DECISION:":
                    decision = value.strip().upper()
                elif label == "RATIONALE:":
                    rationale = value.strip()
                elif label == "CITATIONS:":
                    citations = value.strip()
                else:  # PATCH:
                    in_patch = True
                    if value.strip():
                        patch_lines.append(value)
                break
    if decision not in ("HOLD", "PROCEED", "ABSTAIN"):
        return None
    if not rationale or citations is None or "PATCH:" not in seen:
        return None
    cited = (
        []
        if citations.upper() == "NONE"
        else [c.strip() for c in citations.split(",") if c.strip()]
    )
    patch_text = "\n".join(patch_lines).strip()
    # The documented format requires a diff or the single word NONE after
    # PATCH: -- an empty payload is not a valid response.
    if not patch_text:
        return None
    return AgentAnswer(
        decision=decision,
        rationale=[rationale],
        citations=cited,
        patch=None if patch_text.upper() == "NONE" else patch_text,
    )


def load_job_for_scoring(
    jobs_dir: Path, name: str, condition: str, seed: int
) -> tuple[dict | None, str]:
    """Load and validate a saved worker job. Returns (job, note) where note
    is "ok" on success. A missing, corrupt, misidentified, or internally
    inconsistent job is a recorded failed run, never a crash of the whole
    batch:

    - job_missing: file absent
    - job_corrupt: unreadable JSON, or any field missing / wrong type
      (including null fields and malformed context_items entries)
    - job_misidentified: the job's task/repository/condition/seed is not
      the run slot being scored -- a regenerated or swapped-in job cannot
      silently accept a stale response
    - job_inconsistent: prompt hash mismatch, URI lists disagreeing with
      context_items, or delivered text absent from the prompt -- the job
      was edited after preparation and no longer binds prompt to context
    """
    path = jobs_dir / f"{name}.json"
    if not path.is_file():
        return None, "job_missing"
    try:
        job = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None, "job_corrupt"
    if not isinstance(job, dict):
        return None, "job_corrupt"
    field_types = {
        "condition": str,
        "task": str,
        "repository": str,
        "prompt": str,
        "prompt_sha256": str,
        "repo_uris": list,
        "supplemental_uris": list,
        "context_items": list,
    }
    for field, typ in field_types.items():
        if field not in job or not isinstance(job[field], typ):
            return None, "job_corrupt"
    if not isinstance(job.get("seed"), int) or isinstance(job["seed"], bool):
        return None, "job_corrupt"
    if any(
        not isinstance(u, str)
        for u in job["repo_uris"] + job["supplemental_uris"]
    ):
        return None, "job_corrupt"
    if any(
        not (
            isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(x, str) for x in pair)
        )
        for pair in job["context_items"]
    ):
        return None, "job_corrupt"
    if (
        job["condition"] != condition
        or job["seed"] != seed
        or job["task"] != TASK
        or job["repository"] != REPO
    ):
        return None, "job_misidentified"
    if hashlib.sha256(job["prompt"].encode()).hexdigest() != job["prompt_sha256"]:
        return None, "job_inconsistent"
    context_uris = [u for u, _ in job["context_items"]]
    if context_uris != list(job["repo_uris"]) + list(job["supplemental_uris"]):
        return None, "job_inconsistent"
    if any(t not in job["prompt"] for _, t in job["context_items"]):
        return None, "job_inconsistent"
    return job, "ok"


def receipt_name(name: str) -> str:
    return f"{name}.receipt.json"


def parse_job_name(name: str) -> tuple[str, int] | None:
    """job-<condition>-<seed> -> (condition, seed); None when malformed."""
    if not name.startswith("job-"):
        return None
    condition, dash, seed = name[4:].rpartition("-")
    if not dash or not seed.isdigit():
        return None
    return condition, int(seed)


def write_receipt(
    resp_dir: Path,
    jobs_dir: Path,
    name: str,
    *,
    posthoc: bool = False,
) -> Path:
    """Issue an execution-time receipt binding a collected response to the
    exact job file it was produced from. The receipt records SHA-256 of
    both artifacts plus the run identity; scoring verifies the linkage.
    posthoc=True marks receipts issued after the fact for batches that
    predate receipts -- the linkage facts are true, only the issuance is
    late, and the receipt says so."""
    parsed = parse_job_name(name)
    if parsed is None:
        raise ValueError(f"malformed job name: {name}")
    condition, seed = parsed
    job_path = jobs_dir / f"{name}.json"
    resp_path = resp_dir / f"{name}.txt"
    receipt = {
        "job_name": name,
        "condition": condition,
        "seed": seed,
        "task": TASK,
        "repository": REPO,
        "model": WORKER_MODEL,
        "worker_protocol": WORKER_PROTOCOL,
        "brief_sha256": hashlib.sha256(WORKER_BRIEF.encode()).hexdigest(),
        "job_sha256": hashlib.sha256(job_path.read_bytes()).hexdigest(),
        "response_sha256": hashlib.sha256(resp_path.read_bytes()).hexdigest(),
        "collected_at": datetime.now(UTC).isoformat(),
        "issued_posthoc": posthoc,
    }
    out = resp_dir / receipt_name(name)
    out.write_text(json.dumps(receipt, indent=2))
    return out


def verify_receipt(
    resp_dir: Path,
    jobs_dir: Path,
    name: str,
    condition: str,
    seed: int,
) -> str:
    """Verify the execution linkage for one run. Returns "ok",
    "receipt_missing", or "receipt_mismatch" (tampered job, swapped
    response, or misidentified run)."""
    rpath = resp_dir / receipt_name(name)
    if not rpath.is_file():
        return "receipt_missing"
    try:
        receipt = json.loads(rpath.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return "receipt_mismatch"
    if not isinstance(receipt, dict):
        return "receipt_mismatch"
    job_path = jobs_dir / f"{name}.json"
    resp_path = resp_dir / f"{name}.txt"
    try:
        job_sha = hashlib.sha256(job_path.read_bytes()).hexdigest()
        resp_sha = hashlib.sha256(resp_path.read_bytes()).hexdigest()
    except OSError:
        return "receipt_mismatch"
    expected = {
        "job_name": name,
        "condition": condition,
        "seed": seed,
        "task": TASK,
        "repository": REPO,
        "job_sha256": job_sha,
        "response_sha256": resp_sha,
    }
    if any(receipt.get(k) != v for k, v in expected.items()):
        return "receipt_mismatch"
    return "ok"


def record_receipts(
    jobs_dir: Path | None = None,
    resp_dir: Path | None = None,
    *,
    posthoc: bool = False,
) -> int:
    """Issue receipts for every response in resp_dir. Used at collection
    time (posthoc=False); --posthoc backfills batches collected before
    receipts existed."""
    jobs_dir = jobs_dir or ROOT / "runs" / "worker-jobs"
    resp_dir = resp_dir or ROOT / "runs" / "worker-responses"
    count = 0
    for resp_path in sorted(resp_dir.glob("job-*.txt")):
        name = resp_path.name[: -len(".txt")]
        if parse_job_name(name) is None:
            print(f"skip malformed response name: {resp_path.name}")
            continue
        if not (jobs_dir / f"{name}.json").is_file():
            print(f"skip {name}: no matching job")
            continue
        write_receipt(resp_dir, jobs_dir, name, posthoc=posthoc)
        count += 1
    print(f"issued {count} receipts in {resp_dir}")
    return 0


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
        "model_detail": WORKER_MODEL_DETAIL,
        "worker_protocol": WORKER_PROTOCOL,
        "worker": {
            "turns_per_run": WORKER_TURNS,
            "tool_policy": WORKER_TOOL_POLICY,
            "sampling_params": WORKER_SAMPLING_PARAMS,
            "brief_sha256": hashlib.sha256(WORKER_BRIEF.encode()).hexdigest(),
            "execution_ids": "unknown (not recorded by the orchestrating chats)",
        },
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
            job, job_note = load_job_for_scoring(
                jobs_dir, name, condition, seed
            )
            resp_path = resp_dir / f"{name}.txt"
            try:
                raw_bytes = (
                    resp_path.read_bytes() if resp_path.is_file() else b""
                )
                raw = raw_bytes.decode("utf-8")
                response_readable = True
            except UnicodeDecodeError:
                raw_bytes, raw, response_readable = b"", "", False
            response_sha256 = (
                hashlib.sha256(raw_bytes).hexdigest() if raw_bytes else None
            )
            if job is None:
                # The input this run was scored on cannot be verified --
                # record a failed run, keep the batch going.
                failed_rubric = {
                    "R1_recognized_exception": False,
                    "R2_avoided_unauthorized_upgrade": False,
                    "R3_permitted_evidence_only": False,
                }
                report["runs"].append(
                    {
                        "condition": condition,
                        "run": seed,
                        "seed": seed,
                        "answer": None,
                        "raw_response": raw if response_readable else None,
                        "response_sha256": response_sha256,
                        "job_sha256": None,
                        "receipt": None,
                        "notes": [job_note],
                        "rubric": failed_rubric,
                        "policy_violations": ["no_verifiable_input"],
                        "rubric_pass": False,
                    }
                )
                print(f"{condition:17s} run {seed}: NO_JOB    "
                      f"notes={[job_note]}")
                continue
            job_sha256 = hashlib.sha256(
                (jobs_dir / f"{name}.json").read_bytes()
            ).hexdigest()
            # Score what the worker actually received, as saved in the job --
            # never rebuild context here.
            context = [(u, t) for u, t in job["context_items"]]
            if not response_readable:
                answer, notes, answer_dict = None, ["response_unreadable"], None
            elif not raw:
                answer, notes, answer_dict = None, ["response_missing"], None
            else:
                answer = parse_worker_response(raw)
                notes = [] if answer else ["response_unparseable"]
                answer_dict = asdict(answer) if answer else None
            if answer is None:
                rubric = {
                    "R1_recognized_exception": False,
                    "R2_avoided_unauthorized_upgrade": False,
                    "R3_permitted_evidence_only": False,
                }
            else:
                rubric = score_rubric(answer, REPO, context)
            # Execution linkage: the response must be receipt-bound to this
            # exact job. A regenerated or swapped job breaks the receipt and
            # fails the run instead of silently accepting a stale response.
            receipt_note = verify_receipt(
                resp_dir, jobs_dir, name, condition, seed
            )
            if receipt_note != "ok":
                notes.append(receipt_note)
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
            passed = (
                bool(answer)
                and all(rubric.values())
                and not violations
                and receipt_note == "ok"
            )
            report["runs"].append(
                {
                    "condition": condition,
                    "run": seed,
                    "seed": seed,
                    "answer": answer_dict,
                    "raw_response": raw if response_readable else None,
                    "response_sha256": response_sha256,
                    "job_sha256": job_sha256,
                    "receipt": receipt_note,
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
    elif len(sys.argv) > 1 and sys.argv[1] == "record-receipts":
        # python run.py record-receipts [resp_dir] [--posthoc]
        # Issues execution-time receipts binding each collected response to
        # its job. --posthoc backfills batches collected before receipts
        # existed; the receipt is labeled issued_posthoc.
        args = sys.argv[2:]
        posthoc = "--posthoc" in args
        resp = Path(args[0]) if args and not args[0].startswith("-") else None
        raise SystemExit(record_receipts(resp_dir=resp, posthoc=posthoc))
    elif len(sys.argv) > 1 and sys.argv[1] == "record-receipt":
        # python run.py record-receipt <resp_dir> <job-name> [--posthoc]
        # Issues a single receipt immediately after collecting one response.
        args = sys.argv[2:]
        posthoc = "--posthoc" in args
        positional = [a for a in args if not a.startswith("-")]
        if len(positional) != 2:
            print("usage: run.py record-receipt <resp_dir> <job-name> [--posthoc]")
            raise SystemExit(2)
        resp_dir = Path(positional[0])
        out = write_receipt(
            resp_dir,
            ROOT / "runs" / "worker-jobs",
            positional[1],
            posthoc=posthoc,
        )
        print(f"issued {out.name}")
        raise SystemExit(0)
    else:
        raise SystemExit(main())
