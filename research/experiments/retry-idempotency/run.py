"""Measured worker execution for the retry/idempotency experiment (#5).

Three conditions x three independent worker trials on one coding task:

  repo-only:         fixture files only (worker.py + gateway.py), no
                     supplemental material
  generic-retrieval: fixture files + the equivalent ordinary corpus
                     (retry-policy.md, idempotency-guide.md)
  repo-memory:       fixture files + EA-002 / EA-006 as delivered by
                     ContextAssembler.for_caller to an authorized caller
                     (incident provenance redacted, per the hooks)

The workers are subagents (Muse Spark). Each worker reads ONLY its assigned
job file, produces exactly one response containing the complete new
worker.py, then stops. Outcome scoring is fully mechanical: the produced
file is applied to an isolated fixture copy and exercised by
evaluator/rubric.py (R1-R5). No LLM takes part in scoring, so there is no
scorer judgment to blind -- the blinding that matters is the
orchestrating conversation's lack of experiment history, recorded as
explicit report metadata. The 2026-10-05 fresh batch was spawned from the
main chat (experiment history present in orchestrating context) with
job-file-only worker briefs; the report records this as a limitation.

Flow:
  1. python run.py prepare-workers   -> writes runs/worker-jobs/*.json
  2. one worker trial per job file, fixed brief, single response, no tools
     (prefer a fresh side chat with no experiment history; do not consult
     memory)
  3. after collecting each response, immediately issue its receipt:
     python run.py record-receipt <resp_dir> <job-name>
  4. python run.py score-workers     -> mechanical scoring -> report JSON

Honesty notes:
- The three trials within a condition receive byte-identical context;
  variation comes only from independent sampling. The manifest records
  this (identical prompt hashes within a condition).
- The fixture's gateway docstrings describe gateway mechanics (same key
  deduplicates; PermanentError is non-retryable). The organizational
  mandates -- keys must survive retry boundaries as a standing rule, and
  retry must exist at exactly one orchestration layer -- live only in the
  supplemental context. The measurement is the pass rate across three
  independent trials per condition, not whether a perfect reader could
  pass from the fixture alone.
- Three trials per condition on one task do not establish general
  superiority in either direction.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FIXTURE = ROOT / "fixture"
CORPUS = ROOT / "corpus"
EVALUATOR = ROOT / "evaluator"
SCHEMA = REPO_ROOT / "spec" / "engineering-assertion.schema.json"
EA_FILES = [
    REPO_ROOT / "examples" / "payments" / "idempotency-constraint.json",  # EA-002
    REPO_ROOT / "examples" / "payments" / "current-retry-policy.json",  # EA-006
]
SRC = REPO_ROOT / "src" / "repo_memory"

sys.path.insert(0, str(SRC.parent))
sys.path.insert(0, str(EVALUATOR))

from rubric import score_variant  # noqa: E402

from repo_memory.context import (  # noqa: E402
    Caller,
    ContextAssembler,
    ContextRequest,
    RepositoryMetadata,
)
from repo_memory.loader import load_assertion  # noqa: E402
from repo_memory.models import Scope  # noqa: E402
from repo_memory.policy import ResolutionContext  # noqa: E402

TASK = "Add retry handling for transient settlement submission failures in settle_batch."
REPOSITORY = "payment-worker"
CONDITIONS = ("repo-only", "generic-retrieval", "repo-memory")
RUNS_PER_CONDITION = 3
EXPERIMENT = "retry-idempotency-worker-01"
NOW = datetime(2026, 10, 4, tzinfo=UTC)

# The orchestrating conversation must contain no experiment history
# (e.g. a fresh side chat). Workers never see the reference solution,
# the invalid variants, or the rubric.
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
You are an engineer implementing a change in the payment-worker repository.

TASK: {task}

You receive CONTEXT as numbered items. Each item starts with its source URI
in brackets, e.g. [fixture/worker.py].

RULES (follow exactly):
- Respond exactly once, in one message. Do not use any tools.
- Implement the task by producing a new version of worker.py (the file shown
  as [fixture/worker.py]).
- Keep the change minimal: modify only what the task requires. Do not
  restructure unrelated code.
- Follow every constraint stated in the CONTEXT items. They carry
  organizational rules that the repository alone does not explain.

OUTPUT FORMAT:
- Your response must contain the complete, self-contained new worker.py.
- You may wrap it in a single ```python fenced code block. If you do, only
  the first fenced python block is used; anything outside it is ignored.
- If you do not use a fence, the entire response is used as the file.
- Brief code comments are welcome. Do not add explanations outside the code.

CONTEXT:
{context}\
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_items() -> list[tuple[str, str]]:
    return [
        ("fixture/worker.py", (FIXTURE / "worker.py").read_text()),
        ("fixture/gateway.py", (FIXTURE / "gateway.py").read_text()),
    ]


def render_assertion(a) -> str:
    """Render one assembled assertion the way the caller receives it:
    content, scope, and provenance with restricted entries redacted by
    the authorization hooks.

    The rationale is deliberately withheld: it carries restricted
    incident background (INC-412/INC-463), which the knowledge boundary
    withholds in all arms. Only the permitted rule content is delivered.
    """
    prov = "; ".join(
        f"{p.type}: {p.uri}" for p in a.provenance
    )
    applies = getattr(a, "applies_to", None)
    targets = (
        ", ".join(f"{t.kind}/{t.id}" for t in applies) if applies else "unspecified"
    )
    lines = [
        f"[{a.id}] (status: {a.status}, type: {a.type})",
        f"Content: {a.content}",
    ]
    scope = a.scope
    lines.append(
        f"Scope: {scope.organization} / {scope.domain} / {scope.system}. "
        f"Applies to: {targets}."
    )
    lines.append(f"Provenance: {prov}")
    return "\n".join(lines)


def corpus_docs() -> list[tuple[str, str]]:
    """The shared ordinary documents. Both retrieval arms receive these:
    they carry the same underlying facts as EA-002/EA-006 in ordinary
    prose, so the arms differ only in delivery form (documents vs
    structured assertions), not in permitted facts."""
    return [
        ("corpus/retry-policy.md", (CORPUS / "retry-policy.md").read_text()),
        ("corpus/idempotency-guide.md", (CORPUS / "idempotency-guide.md").read_text()),
    ]


def repo_memory_supplemental() -> list[tuple[str, str]]:
    assertions = [load_assertion(p, SCHEMA) for p in EA_FILES]
    request = ContextRequest(
        task=TASK,
        resolution=ResolutionContext(
            scope=Scope(
                organization="Acme",
                domain="Payments",
                system="Settlement Platform",
                repository=REPOSITORY,
            ),
            when=NOW,
        ),
        repository=RepositoryMetadata(
            name=REPOSITORY, language="python", build_tool="none"
        ),
        evidence_budget=5,
    )
    context = ContextAssembler.for_caller(
        EVAL_CALLER, providers=()
    ).assemble(tuple(assertions), request)
    return [(f"ea:{a.id}", render_assertion(a)) for a in context.assertions]


def build_condition(condition: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (repo_items, supplemental_items). Repo items are identical
    for every condition; only the supplemental path differs. Both
    retrieval arms receive the shared ordinary documents; the memory arm
    additionally receives the structured EA assertions."""
    repo = repo_items()
    if condition == "repo-only":
        return repo, []
    if condition == "generic-retrieval":
        return repo, corpus_docs()
    if condition == "repo-memory":
        return repo, corpus_docs() + repo_memory_supplemental()
    raise ValueError(condition)


def worker_job_prompt(context: list[tuple[str, str]]) -> str:
    numbered = "\n\n".join(f"[{u}]\n{t}" for u, t in context)
    return WORKER_PROMPT.format(task=TASK, context=numbered)


def input_manifest() -> dict:
    files = [p for p in sorted(FIXTURE.glob("*.py")) if p.is_file()]
    files += [p for p in sorted(CORPUS.glob("*.md")) if p.is_file()]
    files += EA_FILES
    files += [p for p in sorted(EVALUATOR.glob("*.py")) if p.is_file()]
    files += [p for p in sorted(SRC.glob("*.py"))]
    files += [SCHEMA, Path(__file__).resolve()]
    hashes = {str(p.relative_to(REPO_ROOT)): sha256_file(p) for p in files}
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=REPO_ROOT
        ).strip()
        porcelain = subprocess.check_output(
            ["git", "status", "--porcelain"], text=True, cwd=REPO_ROOT
        )
        # The experiment runs/ directory is not an effective input (its
        # contents are never hashed), so it does not dirty the manifest.
        dirty = any(
            "research/experiments/retry-idempotency/runs/" not in line
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
            "experiment": EXPERIMENT,
            "task": TASK,
            "repository": REPOSITORY,
            "conditions": list(CONDITIONS),
            "runs_per_condition": RUNS_PER_CONDITION,
        },
    }


def prepare_worker_jobs(dest: Path | None = None) -> list[str]:
    """Write one job file per condition x run with the exact prepared context."""
    jobs_dir = dest if dest else ROOT / "runs" / "worker-jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    manifest = input_manifest()
    paths = []
    for condition in CONDITIONS:
        repo, supplemental = build_condition(condition)
        context_items = repo + supplemental
        prompt = worker_job_prompt(context_items)
        for run in range(RUNS_PER_CONDITION):
            name = f"job-{condition}-{run}"
            job = {
                "condition": condition,
                "run": run,
                "task": TASK,
                "repository": REPOSITORY,
                "prompt": prompt,
                # Binds the prompt to the job: scoring rejects any job
                # whose prompt was edited after preparation.
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "repo_uris": [u for u, _ in repo],
                "supplemental_uris": [u for u, _ in supplemental],
                # The exact delivered context the worker received, as
                # [uri, text] pairs. Scoring reads this back; it never
                # rebuilds context, so the score always reflects what the
                # worker actually saw.
                "context_items": [[u, t] for u, t in context_items],
                "manifest": manifest,
            }
            path = jobs_dir / f"{name}.json"
            path.write_text(json.dumps(job, indent=2))
            paths.append(str(path))
    return paths


def parse_job_name(name: str) -> tuple[str, int] | None:
    """job-<condition>-<run> -> (condition, run); None when malformed."""
    if not name.startswith("job-"):
        return None
    condition, dash, run = name[4:].rpartition("-")
    if not dash or not run.isdigit():
        return None
    return condition, int(run)


def load_job_for_scoring(
    jobs_dir: Path, name: str, condition: str, run: int
) -> tuple[dict | None, str]:
    """Verify a job file before scoring. Returns (job, note); job is None
    when the input this run would be scored on cannot be verified.

    Never raises: a malformed job is recorded as a failed run, it must
    not abort the batch."""
    try:
        return _load_job_for_scoring(jobs_dir, name, condition, run)
    except Exception as exc:  # noqa: BLE001 -- malformed input, not a bug
        return None, f"job_malformed: {type(exc).__name__}"


# The delivery protocol each condition's job must satisfy. Both
# retrieval arms receive the same shared ordinary documents; the memory
# arm additionally receives the structured assertions. Withheld incident
# identifiers must appear in no delivered prompt.
EXPECTED_SUPPLEMENTAL_URIS = {
    "repo-only": [],
    "generic-retrieval": ["corpus/retry-policy.md", "corpus/idempotency-guide.md"],
    "repo-memory": [
        "corpus/retry-policy.md",
        "corpus/idempotency-guide.md",
        "ea:EA-002",
        "ea:EA-006",
    ],
}
WITHHELD_IDENTIFIERS = ("INC-412", "INC-463")


def _load_job_for_scoring(
    jobs_dir: Path, name: str, condition: str, run: int
) -> tuple[dict | None, str]:
    job_path = jobs_dir / f"{name}.json"
    try:
        job = json.loads(job_path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None, "job_unreadable"
    if not isinstance(job, dict):
        return None, "job_corrupt"
    for key in ("condition", "run", "task", "prompt", "prompt_sha256", "context_items"):
        if key not in job:
            return None, "job_corrupt"
    if job["condition"] != condition or job["run"] != run:
        return None, "job_misidentified"
    if job["task"] != TASK:
        return None, "job_inconsistent"
    if hashlib.sha256(job["prompt"].encode()).hexdigest() != job["prompt_sha256"]:
        return None, "job_tampered"
    prompt = worker_job_prompt(
        [(u, t) for u, t in job["context_items"]]
    )
    if hashlib.sha256(prompt.encode()).hexdigest() != job["prompt_sha256"]:
        return None, "job_inconsistent"
    # Delivered-context compliance: the job must carry exactly the
    # supplemental documents its condition's protocol requires, and no
    # withheld identifiers. A job that violates the delivery protocol
    # is not a valid trial input, even if its hashes verify.
    if job.get("supplemental_uris") != EXPECTED_SUPPLEMENTAL_URIS.get(condition):
        return None, "job_context_violation: supplemental_uris"
    for ident in WITHHELD_IDENTIFIERS:
        if ident in job["prompt"]:
            return None, "job_context_violation: withheld_identifier"
    return job, "ok"


def receipt_name(name: str) -> str:
    return f"{name}.receipt.json"


class ReceiptConflictError(Exception):
    """A receipt already exists for this run with different content.

    Receipts are evidence: they are never silently overwritten. A
    conflict means the job or response changed after the receipt was
    issued -- fail on the drift instead of regenerating the receipt to
    repair the mismatch."""


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
    Issue immediately after collecting each response (posthoc=False).

    Raises ReceiptConflictError if a receipt already exists with
    different content. Re-issuing an identical receipt is idempotent and
    keeps the original collected_at.
    """
    parsed = parse_job_name(name)
    if parsed is None:
        raise ValueError(f"malformed job name: {name}")
    condition, run = parsed
    job_path = jobs_dir / f"{name}.json"
    resp_path = resp_dir / f"{name}.txt"
    receipt = {
        "job_name": name,
        "condition": condition,
        "run": run,
        "task": TASK,
        "repository": REPOSITORY,
        "model": WORKER_MODEL,
        "worker_protocol": WORKER_PROTOCOL,
        "brief_sha256": hashlib.sha256(WORKER_BRIEF.encode()).hexdigest(),
        "job_sha256": hashlib.sha256(job_path.read_bytes()).hexdigest(),
        "response_sha256": hashlib.sha256(resp_path.read_bytes()).hexdigest(),
        "collected_at": datetime.now(UTC).isoformat(),
        "issued_posthoc": posthoc,
    }
    out = resp_dir / receipt_name(name)
    if out.is_file():
        try:
            existing = json.loads(out.read_text())
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            existing = None
        if (
            isinstance(existing, dict)
            and existing.get("job_sha256") == receipt["job_sha256"]
            and existing.get("response_sha256") == receipt["response_sha256"]
        ):
            return out
        raise ReceiptConflictError(
            f"receipt for {name} already exists with different content; "
            "refusing to overwrite"
        )
    out.write_text(json.dumps(receipt, indent=2))
    return out


def verify_receipt(
    resp_dir: Path,
    jobs_dir: Path,
    name: str,
    condition: str,
    run: int,
) -> str:
    """Verify the execution linkage for one run. Returns "ok",
    "receipt_missing", "receipt_mismatch" (tampered job, swapped
    response, or misidentified run), "receipt_metadata_mismatch"
    (the recorded execution metadata does not match this experiment's
    protocol), or "receipt_posthoc" (the linkage verifies but the
    receipt was issued after the fact -- preserved as evidence, excluded
    from capture-time-qualified outcomes)."""
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
        "run": run,
        "task": TASK,
        "repository": REPOSITORY,
        "job_sha256": job_sha,
        "response_sha256": resp_sha,
    }
    if any(receipt.get(k) != v for k, v in expected.items()):
        return "receipt_mismatch"
    # Execution metadata must describe this experiment's protocol; a
    # receipt from a different model, brief, or protocol version is not
    # evidence for this batch.
    meta_expected = {
        "model": WORKER_MODEL,
        "worker_protocol": WORKER_PROTOCOL,
        "brief_sha256": hashlib.sha256(WORKER_BRIEF.encode()).hexdigest(),
    }
    if any(receipt.get(k) != v for k, v in meta_expected.items()):
        return "receipt_metadata_mismatch"
    try:
        datetime.fromisoformat(receipt["collected_at"])
    except (KeyError, TypeError, ValueError):
        return "receipt_metadata_mismatch"
    if not isinstance(receipt.get("issued_posthoc"), bool):
        return "receipt_metadata_mismatch"
    if receipt["issued_posthoc"]:
        return "receipt_posthoc"
    return "ok"


def record_receipts(
    jobs_dir: Path | None = None,
    resp_dir: Path | None = None,
    *,
    posthoc: bool = False,
) -> int:
    """Issue receipts for every response in resp_dir. Used at collection
    time (posthoc=False)."""
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
        try:
            write_receipt(resp_dir, jobs_dir, name, posthoc=posthoc)
        except ReceiptConflictError as exc:
            print(f"skip {name}: {exc}")
            continue
        except OSError as exc:
            print(f"skip {name}: cannot read job/response ({exc})")
            continue
        count += 1
    print(f"issued {count} receipts in {resp_dir}")
    return 0


FENCE_RE = re.compile(r"```python\s*\n(.*?)```", re.S)
BARE_FENCE_RE = re.compile(r"```\s*\n(.*?)```", re.S)


def extract_worker_py(raw: str) -> tuple[str, str]:
    """Pull the candidate worker.py out of a worker response. Returns
    (code, extraction_note)."""
    m = FENCE_RE.search(raw)
    if m:
        return m.group(1), "fenced-python"
    m = BARE_FENCE_RE.search(raw)
    if m:
        return m.group(1), "fenced-bare"
    return raw.strip(), "unfenced"


def score_worker_responses(
    jobs_dir: Path | None = None,
    resp_dir: Path | None = None,
    tag: str = "worker",
    out_dir: Path | None = None,
) -> int:
    """Mechanically score recorded worker responses into a report.

    Scoring reads the saved job files (the exact context each worker
    received); it never rebuilds context. Each produced worker.py is
    applied to an isolated fixture copy and exercised by the predeclared
    rubric -- no LLM takes part in scoring. Blinding is explicit protocol
    metadata: the orchestrating conversation held no experiment history.
    """
    jobs_dir = jobs_dir or ROOT / "runs" / "worker-jobs"
    resp_dir = resp_dir or ROOT / "runs" / "worker-responses"
    extracted_dir = resp_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    manifest = input_manifest()
    report: dict = {
        "experiment": EXPERIMENT,
        "task": TASK,
        "repository": REPOSITORY,
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
        "conditions": list(CONDITIONS),
        "runs_per_condition": RUNS_PER_CONDITION,
        # Explicit protocol metadata. Scoring itself is deterministic
        # code, so there is no scorer judgment to blind. Worker blinding:
        # the fresh 2026-10-05 batch was spawned from the main chat, whose
        # context holds experiment history (rubric, reference solution,
        # invalid variants, exploratory-batch scores). Each worker's brief
        # constrained it to read ONLY its assigned job file and produce
        # one response, so the workers' effective task information was the
        # job file -- but unlike the exploratory batch (orchestrated from
        # a fresh side chat), strict orchestration-level blinding did not
        # hold. Recorded here as a limitation, not a claim.
        "blinded": False,
        "blinding_note": (
            "Workers spawned from the main chat (experiment history in "
            "orchestrating context); worker briefs restricted each worker "
            "to its assigned job file only. See code comment."
        ),
        "scoring": (
            "mechanical: evaluator/rubric.py R1-R5 on the produced worker.py; "
            "no LLM in scoring"
        ),
        "runs": [],
    }
    for condition in CONDITIONS:
        for run in range(RUNS_PER_CONDITION):
            name = f"job-{condition}-{run}"
            job, job_note = load_job_for_scoring(jobs_dir, name, condition, run)
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
            receipt_status = verify_receipt(resp_dir, jobs_dir, name, condition, run)
            row: dict = {
                "condition": condition,
                "run": run,
                "job_name": name,
                "response_sha256": response_sha256,
                "job_sha256": (
                    hashlib.sha256(
                        (jobs_dir / f"{name}.json").read_bytes()
                    ).hexdigest()
                    if (jobs_dir / f"{name}.json").is_file()
                    else None
                ),
                "receipt": receipt_status,
                "notes": [],
            }
            if receipt_status != "ok":
                # An unverified run is not a valid outcome: a missing,
                # mismatched, or metadata-invalid receipt can never count
                # as a pass, no matter what the response scores. A posthoc
                # receipt is preserved as evidence but excluded from
                # capture-time-qualified outcomes.
                if receipt_status == "receipt_posthoc":
                    row["notes"].append(
                        "receipt_posthoc: linkage preserved, excluded from "
                        "capture-time-qualified outcomes"
                    )
                else:
                    row["notes"].append(f"receipt_{receipt_status}")
                row["rubric"] = {f"R{i}": False for i in range(1, 6)}
                row["rubric_pass"] = False
                report["runs"].append(row)
                print(
                    f"{condition:17s} run {run}: "
                    f"RECEIPT_{receipt_status.upper()} -> fail"
                )
                continue
            if job is None:
                row["notes"].append(job_note)
                row["rubric"] = {f"R{i}": False for i in range(1, 6)}
                row["rubric_pass"] = False
                report["runs"].append(row)
                print(f"{condition:17s} run {run}: NO_JOB notes={[job_note]}")
                continue
            if not raw_bytes or not response_readable:
                row["notes"].append("response_missing_or_undecodable")
                row["rubric"] = {f"R{i}": False for i in range(1, 6)}
                row["rubric_pass"] = False
                report["runs"].append(row)
                print(f"{condition:17s} run {run}: NO_RESPONSE")
                continue
            code, extraction = extract_worker_py(raw)
            row["extraction"] = extraction
            if not code.strip():
                row["notes"].append("empty_extraction")
                row["rubric"] = {f"R{i}": False for i in range(1, 6)}
                row["rubric_pass"] = False
                report["runs"].append(row)
                print(f"{condition:17s} run {run}: EMPTY")
                continue
            variant_path = extracted_dir / f"{name}.worker.py"
            variant_path.write_text(code)
            try:
                result = score_variant(variant_path)
            except Exception as exc:  # mechanical failure, not a judgment call
                row["notes"].append(f"scorer_error: {type(exc).__name__}")
                row["rubric"] = {f"R{i}": False for i in range(1, 6)}
                row["rubric_pass"] = False
                report["runs"].append(row)
                print(f"{condition:17s} run {run}: SCORER_ERROR {exc}")
                continue
            checks = result.get("checks", {})
            row["rubric"] = {k: bool(v) for k, v in checks.items()}
            row["rubric_detail"] = result.get("detail", {})
            row["rubric_pass"] = all(checks.values()) if checks else False
            report["runs"].append(row)
            passed = sum(1 for v in checks.values() if v)
            print(
                f"{condition:17s} run {run}: "
                f"{'PASS' if row['rubric_pass'] else 'fail'} "
                f"({passed}/{len(checks)}) receipt={receipt_status}"
            )
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out = (out_dir or ROOT / "runs") / f"worker-{tag}-{stamp}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"report: {out}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "prepare-workers":
        # python run.py prepare-workers
        paths = prepare_worker_jobs()
        print(f"wrote {len(paths)} job files")
        return 0
    if len(argv) > 1 and argv[1] == "record-receipt":
        # python run.py record-receipt <resp_dir> <job-name>
        if len(argv) < 4:
            print("usage: run.py record-receipt <resp_dir> <job-name>")
            return 2
        resp_dir = Path(argv[2])
        jobs_dir = ROOT / "runs" / "worker-jobs"
        write_receipt(resp_dir, jobs_dir, argv[3])
        print(f"receipt issued for {argv[3]}")
        return 0
    if len(argv) > 1 and argv[1] == "record-receipts":
        # python run.py record-receipts [resp_dir]
        resp = Path(argv[2]) if len(argv) > 2 else None
        return record_receipts(resp_dir=resp)
    if len(argv) > 1 and argv[1] == "score-workers":
        # python run.py score-workers [--tag NAME] [--resp-dir DIR]
        tag = "worker"
        resp_dir = None
        args = argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--tag" and i + 1 < len(args):
                tag = args[i + 1]
                i += 2
            elif args[i] == "--resp-dir" and i + 1 < len(args):
                resp_dir = Path(args[i + 1])
                i += 2
            else:
                i += 1
        return score_worker_responses(resp_dir=resp_dir, tag=tag)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
