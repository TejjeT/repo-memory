"""Measured worker execution for the supersession experiment (#5).

Three conditions x three independent worker trials on the retry-configuration
task:

  repo-only:         fixture files only (worker.py + gateway.py), no
                     supplemental material
  generic-retrieval: fixture files + the equivalent ordinary corpus
                     (retry-policy-current.md, retry-policy-history.md)
  repo-memory:       fixture files + EA-005 / EA-006 as delivered by the
                     authenticated MCP read path (handle_tool_call, the
                     same dispatcher the stdio server runs), with
                     restricted incident identifiers withheld

The workers are subagents (Muse Spark). Each worker reads ONLY its assigned
job file, produces exactly one response containing the complete new
worker.py, then stops. Outcome scoring is fully mechanical: the produced
file is applied to an isolated fixture copy and exercised by
evaluator/rubric.py (S1-S3). No LLM takes part in scoring, so there is no
scorer judgment to blind -- the blinding that matters is the
orchestrating conversation's lack of experiment history, recorded as
explicit report metadata.

Flow:
  1. python run.py prepare-workers   -> writes runs/worker-jobs/*.json
  2. one worker trial per job file, fixed brief, single response, no tools
  3. after collecting each response, immediately issue its receipt:
     python run.py record-receipt <resp_dir> <job-name>
  4. python run.py score-workers     -> mechanical scoring -> report JSON

Honesty notes:
- The three trials within a condition receive byte-identical context;
  variation comes only from independent sampling. The manifest records
  this (identical prompt hashes within a condition).
- The fixture's gateway has the stale EA-005 value (3) baked in. The
  organizational mandate -- current policy requires exactly one retry
  layer, worker-owned, gateway at 0 -- lives only in the supplemental
  context. The measurement is the pass rate across three independent
  trials per condition, not whether a perfect reader could pass from the
  fixture alone.
- Three trials per condition on one task do not establish general
  superiority in either direction. Ties are valid outcomes.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FIXTURE = ROOT / "fixture"
CORPUS = ROOT / "corpus"
EVALUATOR = ROOT / "evaluator"

SRC = REPO_ROOT / "src" / "repo_memory"
sys.path.insert(0, str(SRC.parent))
sys.path.insert(0, str(EVALUATOR))

from rubric import evaluate as evaluate_variant  # noqa: E402

from repo_memory.auth import VerifiedSession  # noqa: E402
from repo_memory.models import (  # noqa: E402
    EngineeringAssertion,
    Provenance,
    Scope,
)
from repo_memory.tools import handle_tool_call  # noqa: E402

TASK = (
    "Bring the settlement retry configuration into compliance with "
    "current policy (see fixture/worker.py)."
)
REPOSITORY = "payment-worker"
CONDITIONS = ("repo-only", "generic-retrieval", "repo-memory")
RUNS_PER_CONDITION = 3
EXPERIMENT = "supersession-worker-01"
NOW = datetime(2026, 10, 8, tzinfo=UTC)

# The orchestrating conversation must contain no experiment history.
# Workers never see the reference solution, the invalid variants, or
# the rubric.
MCP_CALLER_GRANTS = ("doc://",)  # incident:// withheld
MCP_SESSION_TOKEN = "agent-token"

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
- Some CONTEXT items may describe HISTORICAL guidance marked superseded.
  Superseded guidance is not current policy; follow the current items.

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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def repo_items() -> list[tuple[str, str]]:
    return [
        ("fixture/worker.py", (FIXTURE / "worker.py").read_text()),
        ("fixture/gateway.py", (FIXTURE / "gateway.py").read_text()),
    ]


def corpus_docs() -> list[tuple[str, str]]:
    """The shared ordinary documents. Both retrieval arms receive these:
    they carry the same underlying facts as EA-005/EA-006 in ordinary
    prose, so the arms differ only in delivery form (documents vs
    structured MCP assertions), not in permitted facts."""
    return [
        (
            "corpus/retry-policy-current.md",
            (CORPUS / "retry-policy-current.md").read_text(),
        ),
        (
            "corpus/retry-policy-history.md",
            (CORPUS / "retry-policy-history.md").read_text(),
        ),
    ]


def _mcp_assertions() -> tuple[EngineeringAssertion, ...]:
    scope = Scope(
        organization="Acme", domain="Payments", system="Settlement Platform"
    )
    ea005 = EngineeringAssertion(
        id="EA-005",
        type="constraint",
        content="Gateway retries may be configured up to three attempts.",
        scope=scope,
        status="superseded",
        importance="high",
        provenance=(Provenance(type="document", uri="doc://acme/adr/0029"),),
        created_at=datetime(2025, 8, 1, tzinfo=UTC),
        superseded_by=("EA-006",),
    )
    ea006 = EngineeringAssertion(
        id="EA-006",
        type="incident-derived-constraint",
        content=(
            "Retry must exist at exactly one orchestration layer for "
            "settlement submission; gateway and client retries must not "
            "both be enabled."
        ),
        scope=scope,
        status="approved",
        importance="critical",
        provenance=(
            Provenance(type="incident", uri="incident://INC-463"),
            Provenance(type="document", uri="doc://acme/adr/0041"),
        ),
        created_at=datetime(2026, 6, 12, tzinfo=UTC),
        supersedes=("EA-005",),
    )
    return (ea005, ea006)


class _Directory:
    def grants_for(self, subject: str) -> tuple[str, ...]:
        return MCP_CALLER_GRANTS


def _resolve(token: str | None) -> VerifiedSession | None:
    if token != MCP_SESSION_TOKEN:
        return None
    return VerifiedSession(subject="agent", authenticated_at=NOW, method="eval")


def _render_mcp_response(label: str, payload: dict) -> str:
    """Render one MCP tool response as the worker sees it: the exact
    JSON the authenticated MCP read path delivers."""
    return f"MCP {label} response (JSON):\n{json.dumps(payload, indent=2)}"


def repo_memory_supplemental() -> list[tuple[str, str]]:
    """EA-005/EA-006 as delivered by the real MCP dispatcher
    (handle_tool_call): memory_search for current guidance plus
    memory_get for the superseded assertion as history. Restricted
    incident identifiers are withheld by the tool path itself."""
    assertions = _mcp_assertions()
    directory = _Directory()
    items: list[tuple[str, str]] = []

    search_payload = handle_tool_call(
        "memory_search",
        {
            "task": TASK,
            "scope": {
                "organization": "Acme",
                "domain": "Payments",
                "system": "Settlement Platform",
            },
            "session_token": MCP_SESSION_TOKEN,
        },
        resolve_session=_resolve,
        directory=directory,
        assertions=assertions,
    )
    items.append(
        ("mcp:memory_search", _render_mcp_response("memory_search", search_payload))
    )

    get_payload = handle_tool_call(
        "memory_get",
        {"assertion_id": "EA-005", "session_token": MCP_SESSION_TOKEN},
        resolve_session=_resolve,
        directory=directory,
        assertions=assertions,
    )
    items.append(
        ("mcp:memory_get:EA-005", _render_mcp_response("memory_get", get_payload))
    )
    return items


def build_condition(condition: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (repo_items, supplemental_items). Repo items are identical
    for every condition; only the supplemental path differs."""
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
    files += [p for p in sorted(EVALUATOR.glob("*.py")) if p.is_file()]
    files += [p for p in sorted(SRC.glob("*.py")) if p.is_file()]
    files += [Path(__file__).resolve()]
    hashes = {str(p.relative_to(REPO_ROOT)): sha256_file(p) for p in files}
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=REPO_ROOT
        ).strip()
        porcelain = subprocess.check_output(
            ["git", "status", "--porcelain"], text=True, cwd=REPO_ROOT
        )
        dirty = any(
            "research/experiments/supersession/runs/" not in line
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
            "blinded": False,
            "blinding_note": (
                "Workers are subagents spawned from the orchestrating "
                "chat, which contains experiment history. Each worker "
                "receives a job-file-only brief and is instructed to read "
                "only that file. Strict blinding (fresh side chats with no "
                "history) was not used; record as a limitation."
            ),
            "worker_model": WORKER_MODEL,
            "worker_model_detail": WORKER_MODEL_DETAIL,
            "worker_protocol": WORKER_PROTOCOL,
            "worker_turns": WORKER_TURNS,
            "worker_tool_policy": WORKER_TOOL_POLICY,
            "worker_sampling_params": WORKER_SAMPLING_PARAMS,
        },
    }


def prepare_worker_jobs(dest: Path | None = None) -> list[str]:
    dest = dest or (ROOT / "runs" / "worker-jobs")
    dest.mkdir(parents=True, exist_ok=True)
    manifest = input_manifest()
    names = []
    for condition in CONDITIONS:
        repo, supplemental = build_condition(condition)
        context = repo + supplemental
        prompt = worker_job_prompt(context)
        prompt_hash = sha256_text(prompt)
        for run in range(1, RUNS_PER_CONDITION + 1):
            name = f"{condition}-r{run}"
            job = {
                "job_name": name,
                "experiment": EXPERIMENT,
                "condition": condition,
                "run": run,
                "task": TASK,
                "prompt": prompt,
                "prompt_sha256": prompt_hash,
                "manifest": manifest,
            }
            (dest / f"{name}.json").write_text(json.dumps(job, indent=2))
            names.append(name)
    return names


def parse_job_name(name: str) -> tuple[str, int] | None:
    m = re.fullmatch(r"(repo-only|generic-retrieval|repo-memory)-r([1-3])", name)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def receipt_name(name: str) -> str:
    return f"receipt-{name}.json"


def write_receipt(
    resp_dir: Path, job_name: str, response_text: str, dest: Path | None = None,
    force: bool = False, reason: str | None = None,
) -> Path:
    """Issue a capture-time receipt for one worker response. The receipt
    hashes the exact response bytes, binds to the job's prompt hash, and
    records when it was captured; it is the tamper-evident link between
    collection and scoring.

    Receipts are immutable: if a receipt already exists for this job,
    it is NOT overwritten unless force=True is passed explicitly with
    a reason. Forced replacements are logged to an append-only audit
    trail (runs/receipts/audit.log).

    The receipt binds to prompt_sha256 from the job file: if the prompt
    changes after the receipt is issued, verification fails. A changed
    prompt cannot pass using the original response receipt.
    """
    dest = dest or (ROOT / "runs" / "receipts")
    dest.mkdir(parents=True, exist_ok=True)
    jobs_dir = ROOT / "runs" / "worker-jobs"
    job_path = jobs_dir / f"{job_name}.json"
    prompt_sha256 = None
    if job_path.exists():
        with suppress(Exception):
            prompt_sha256 = json.loads(job_path.read_text()).get("prompt_sha256")
    path = dest / receipt_name(job_name)
    if path.exists() and not force:
        raise FileExistsError(
            f"receipt already exists for {job_name}; refusing to overwrite "
            f"(pass force=True with a reason for a documented re-issue)"
        )
    binding_type = "capture-time"
    if path.exists() and force:
        if not reason:
            raise ValueError("forced receipt replacement requires a reason")
        # Retroactively added bindings are posthoc attestations, not
        # capture-time evidence. Label them as such.
        binding_type = "posthoc"
        # Audit trail: append-only log of the replacement, preserving
        # the full history (not just the latest).
        old_receipt = json.loads(path.read_text())
        audit_path = dest / "audit.log"
        with open(audit_path, "a") as f:
            f.write(json.dumps({
                "event": "receipt_replaced",
                "job_name": job_name,
                "replaced_at": datetime.now(UTC).isoformat(),
                "old_response_sha256": old_receipt.get("response_sha256"),
                "old_prompt_sha256": old_receipt.get("prompt_sha256"),
                "old_binding_type": old_receipt.get("binding_type"),
                "new_prompt_sha256": prompt_sha256,
                "new_binding_type": binding_type,
                "reason": reason,
            }) + "\n")
    captured_at = datetime.now(UTC).isoformat()
    receipt = {
        "job_name": job_name,
        "experiment": EXPERIMENT,
        "captured_at": captured_at,
        "response_sha256": sha256_text(response_text),
        "response_bytes": len(response_text.encode()),
        "response_path": str(resp_dir),
        "prompt_sha256": prompt_sha256,
        "binding_type": binding_type,
    }
    path.write_text(json.dumps(receipt, indent=2))
    return path


def verify_receipt(
    resp_dir: Path, job_name: str, dest: Path | None = None
) -> tuple[bool, str]:
    """Re-hash the stored response and compare with the receipt. Returns
    (ok, message).

    Validates receipt metadata strictly: a receipt with missing fields,
    wrong job_name, malformed hash, or byte-count mismatch fails even
    if the hash happens to match.
    """
    dest = dest or (ROOT / "runs" / "receipts")
    receipt_path = dest / receipt_name(job_name)
    if not receipt_path.exists():
        return False, "missing receipt"
    try:
        receipt = json.loads(receipt_path.read_text())
    except Exception as e:
        return False, f"receipt unreadable: {e}"
    if not isinstance(receipt, dict):
        return False, "receipt is not an object"

    # Structural validation: required fields must exist with right types.
    # prompt_sha256 is required (non-null): a null binding cannot prove
    # the prompt is unchanged and fails closed.
    required = {
        "job_name": str,
        "experiment": str,
        "captured_at": str,
        "response_sha256": str,
        "response_bytes": int,
        "prompt_sha256": str,
        "binding_type": str,
    }
    for field, ftype in required.items():
        if field not in receipt:
            return False, f"receipt missing field: {field}"
        if not isinstance(receipt[field], ftype):
            return False, f"receipt field {field} has wrong type"

    # Identity validation: receipt must name this job and experiment.
    if receipt["job_name"] != job_name:
        return False, (
            f"receipt job_name mismatch: {receipt['job_name']!r} != {job_name!r}"
        )
    if receipt["experiment"] != EXPERIMENT:
        return False, (
            f"receipt experiment mismatch: {receipt['experiment']!r}"
        )

    # Prompt binding: the receipt is bound to the prompt hash at capture
    # time. If the job's prompt changed since, the receipt is stale and
    # the trial cannot pass on the old response. A null binding fails
    # closed: it cannot prove the prompt is unchanged.
    jobs_dir = ROOT / "runs" / "worker-jobs"
    job_path = jobs_dir / f"{job_name}.json"
    receipt_prompt_hash = receipt.get("prompt_sha256")
    if receipt_prompt_hash is None:
        return False, "receipt has null prompt binding: cannot verify prompt unchanged"
    if job_path.exists():
        try:
            current_prompt_hash = json.loads(job_path.read_text()).get("prompt_sha256")
        except Exception:
            current_prompt_hash = None
        if current_prompt_hash and receipt_prompt_hash != current_prompt_hash:
            return False, (
                f"receipt prompt binding broken: job prompt changed since "
                f"receipt issued (receipt {receipt_prompt_hash[:12]} vs "
                f"job {current_prompt_hash[:12]})"
            )
    # Binding type must be declared: capture-time or posthoc.
    binding_type = receipt.get("binding_type")
    if binding_type not in ("capture-time", "posthoc"):
        return False, (
            f"receipt binding_type must be 'capture-time' or 'posthoc', "
            f"got {binding_type!r}"
        )

    # Hash format validation: must be 64 hex chars (SHA-256).
    h = receipt["response_sha256"]
    if len(h) != 64 or not all(c in "0123456789abcdef" for c in h.lower()):
        return False, "receipt response_sha256 is not a valid SHA-256 hex digest"

    # Timestamp validation: must parse as ISO-8601.
    try:
        datetime.fromisoformat(receipt["captured_at"])
    except Exception:
        return False, "receipt captured_at is not a valid ISO-8601 timestamp"

    # Find the response file in resp_dir (first .md or .txt or raw file).
    candidates = sorted(
        p for p in resp_dir.iterdir() if p.is_file() and p.suffix in (".md", ".txt", ".py")
    )
    if not candidates:
        # Fall back: any single file.
        candidates = sorted(p for p in resp_dir.iterdir() if p.is_file())
    if not candidates:
        return False, "no response file"

    # Byte-count validation: must match actual file size.
    text = candidates[0].read_text()
    actual_bytes = len(text.encode())
    if receipt["response_bytes"] != actual_bytes:
        return False, (
            f"receipt byte-count mismatch: {receipt['response_bytes']} != {actual_bytes}"
        )

    # Hash validation: must match actual content.
    actual = sha256_text(text)
    if actual != receipt["response_sha256"].lower():
        return False, f"hash drift: receipt {receipt['response_sha256'][:12]} vs {actual[:12]}"
    return True, "ok"


def extract_worker_py(raw: str) -> tuple[str, str]:
    """Extract the worker.py from a raw worker response. Returns
    (code, method): method is 'fenced' or 'raw'."""
    m = re.search(r"```python\n(.*?)```", raw, re.DOTALL)
    if m:
        return m.group(1), "fenced"
    return raw, "raw"


def required_manifest_keys() -> set[str]:
    """The set of source paths that must appear in every job manifest's
    input_hashes. A manifest missing any of these is incomplete and
    fails closed -- a one-file manifest must not pass.
    """
    files = [p for p in sorted(FIXTURE.glob("*.py")) if p.is_file()]
    files += [p for p in sorted(CORPUS.glob("*.md")) if p.is_file()]
    files += [p for p in sorted(EVALUATOR.glob("*.py")) if p.is_file()]
    files += [p for p in sorted(SRC.glob("*.py")) if p.is_file()]
    files += [Path(__file__).resolve()]
    return {str(p.relative_to(REPO_ROOT)) for p in files}


def verify_job_inputs(jobs_dir: Path | None = None) -> tuple[bool, str, dict]:
    """Verify that all job files exist and their recorded input hashes
    match the current files. Returns (ok, message, details).

    This is the evidence-integrity gate: scoring must not produce a
    passing report when the inputs it claims to have used are missing
    or have changed.

    Two levels of checking:
    1. Internal: each job's prompt_sha256 must match its prompt (catches
       edits where the hash wasn't updated).
    2. Frozen-source: the manifest's input_hashes must match the actual
       files for prompt-affecting sources (fixture, corpus, src/). A
       mismatch here means the delivered context may differ from what
       was recorded -- fail closed. Non-prompt files (evaluator, runner)
       are reported as warnings; they affect scoring, not what workers saw.
    """
    jobs_dir = jobs_dir or (ROOT / "runs" / "worker-jobs")
    missing = []
    hash_mismatches = []
    source_mismatches = []  # prompt-affecting files that changed
    source_warnings = []  # non-prompt files that changed
    # Paths whose content is embedded in (or generates) the delivered prompt.
    prompt_affecting = (
        "research/experiments/supersession/fixture/",
        "research/experiments/supersession/corpus/",
        "src/repo_memory/",
    )
    for condition in CONDITIONS:
        for run in range(1, RUNS_PER_CONDITION + 1):
            name = f"{condition}-r{run}"
            job_path = jobs_dir / f"{name}.json"
            if not job_path.exists():
                missing.append(name)
                continue
            try:
                job = json.loads(job_path.read_text())
            except Exception as e:
                hash_mismatches.append(f"{name}: unreadable ({e})")
                continue
            # Level 1: internal prompt hash consistency.
            prompt = job.get("prompt", "")
            recorded = job.get("prompt_sha256", "")
            actual = sha256_text(prompt)
            if recorded != actual:
                hash_mismatches.append(f"{name}: prompt hash drift")
            # Level 2: frozen-source hashes from THIS job's manifest.
            # Every job must carry a complete manifest: missing manifest,
            # empty input_hashes, or a manifest omitting required sources
            # all fail closed. A one-file manifest must not pass.
            manifest = job.get("manifest")
            if not isinstance(manifest, dict):
                hash_mismatches.append(f"{name}: missing manifest")
                continue
            recorded_hashes = manifest.get("input_hashes")
            if not isinstance(recorded_hashes, dict) or not recorded_hashes:
                hash_mismatches.append(f"{name}: empty manifest input_hashes")
                continue
            required_keys = required_manifest_keys()
            missing_keys = required_keys - set(recorded_hashes.keys())
            if missing_keys:
                hash_mismatches.append(
                    f"{name}: manifest omits required sources: "
                    f"{', '.join(sorted(missing_keys))}"
                )
                continue
            for rel_path, recorded_hash in recorded_hashes.items():
                full_path = REPO_ROOT / rel_path
                if not full_path.exists():
                    entry = f"{rel_path}: file missing"
                    if entry not in source_mismatches:
                        source_mismatches.append(entry)
                    continue
                actual_hash = sha256_file(full_path)
                if actual_hash != recorded_hash:
                    is_prompt_affecting = rel_path.startswith(prompt_affecting)
                    target = (
                        source_mismatches if is_prompt_affecting
                        else source_warnings
                    )
                    entry = f"{rel_path}: changed since job generation"
                    if entry not in target:
                        target.append(entry)
    details = {
        "missing": missing,
        "hash_mismatches": hash_mismatches,
        "source_mismatches": source_mismatches,
        "source_warnings": source_warnings,
    }
    if missing:
        return False, f"missing job files: {', '.join(missing)}", details
    if hash_mismatches:
        return False, f"job integrity failures: {'; '.join(hash_mismatches)}", details
    if source_mismatches:
        return (
            False,
            f"frozen sources changed: {'; '.join(source_mismatches)}",
            details,
        )
    msg = "all job files present and prompt hashes verify"
    if source_warnings:
        msg += f"; warnings: {'; '.join(source_warnings)}"
    return True, msg, details


def scan_trial_for_leaks(job_path: Path, response_text: str) -> dict:
    """Scan a trial's delivered context and worker response for
    restricted markers. Returns {context_leaks, response_leaks, clean}.

    A worker that cites a restricted incident identifier in its
    response must not count as passing, even if the code scores well.
    """
    from rubric import scan_restricted

    job = json.loads(job_path.read_text())
    context_leaks = scan_restricted(job.get("prompt", ""))
    response_leaks = scan_restricted(response_text)
    return {
        "context_leaks": context_leaks,
        "response_leaks": response_leaks,
        "clean": len(context_leaks) == 0 and len(response_leaks) == 0,
    }


def score_worker_responses(
    resp_root: Path | None = None, dest: Path | None = None
) -> dict:
    """Mechanically score every collected worker response. Returns the
    report dict and writes it to runs/report.json.

    Evidence gates (fail closed):
    - All job files must exist with verifying prompt hashes.
    - Receipts must verify (no hash drift).
    - Worker responses must be free of restricted markers.
    """
    resp_root = resp_root or (ROOT / "runs" / "worker-responses")
    jobs_dir = ROOT / "runs" / "worker-jobs"
    manifest = input_manifest()

    # Gate 1: job inputs must exist and verify.
    jobs_ok, jobs_msg, jobs_details = verify_job_inputs(jobs_dir)
    if not jobs_ok:
        raise FileNotFoundError(f"cannot score: {jobs_msg}")

    results: dict[str, dict] = {}
    for condition in CONDITIONS:
        for run in range(1, RUNS_PER_CONDITION + 1):
            name = f"{condition}-r{run}"
            resp_dir = resp_root / name
            job_path = jobs_dir / f"{name}.json"
            entry: dict = {"job_name": name, "condition": condition, "run": run}
            ok, msg = verify_receipt(resp_dir, name)
            entry["receipt"] = {"ok": ok, "message": msg}
            if not ok:
                entry["scores"] = None
                entry["leak_scan"] = None
                entry["pass"] = False
                results[name] = entry
                continue
            candidates = sorted(
                p
                for p in resp_dir.iterdir()
                if p.is_file() and p.suffix in (".md", ".txt", ".py")
            ) or sorted(p for p in resp_dir.iterdir() if p.is_file())
            raw = candidates[0].read_text()

            # Gate 2: leak scan on delivered context and response.
            leak_scan = scan_trial_for_leaks(job_path, raw)
            entry["leak_scan"] = leak_scan

            code, method = extract_worker_py(raw)
            entry["extract_method"] = method
            tmp = ROOT / "runs" / ".tmp-variants"
            tmp.mkdir(parents=True, exist_ok=True)
            variant_path = tmp / f"{name}-worker.py"
            variant_path.write_text(code)
            try:
                scores = evaluate_variant(variant_path)
            finally:
                variant_path.unlink(missing_ok=True)
            entry["scores"] = scores
            # S1+S2+S3 all true AND no leaks => pass.
            entry["pass"] = (
                isinstance(scores, dict)
                and scores.get("S1") is True
                and scores.get("S2") is True
                and scores.get("S3") is True
                and leak_scan["clean"] is True
            )
            results[name] = entry

    # Aggregate per condition.
    summary = {}
    for condition in CONDITIONS:
        trials = [results[f"{condition}-r{r}"] for r in range(1, RUNS_PER_CONDITION + 1)]
        passed = sum(1 for t in trials if t.get("pass") is True)
        summary[condition] = {
            "trials": len(trials),
            "passed": passed,
            "rate": f"{passed}/{len(trials)}",
        }

    report = {
        "experiment": EXPERIMENT,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest": manifest,
        "input_verification": {
            "ok": jobs_ok,
            "message": jobs_msg,
            "details": jobs_details,
        },
        "results": results,
        "summary": summary,
        "interpretation": (
            "Mechanical scores only. Three trials per condition on one "
            "task do not establish general superiority in either "
            "direction. Ties and negative outcomes are valid."
        ),
    }
    out = (dest or (ROOT / "runs")) / "report.json"
    out.write_text(json.dumps(report, indent=2))
    return report


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: run.py prepare-workers | "
            "record-receipt <resp_dir> <job-name> | score-workers"
        )
        return 2
    cmd = argv[1]
    if cmd == "prepare-workers":
        names = prepare_worker_jobs()
        print(f"wrote {len(names)} job files: {', '.join(names)}")
        return 0
    if cmd == "record-receipt":
        if len(argv) != 4:
            print("usage: run.py record-receipt <resp_dir> <job-name>")
            return 2
        resp_dir = Path(argv[2])
        # Read response from stdin (piped) or from the newest file in resp_dir.
        if not sys.stdin.isatty():
            response_text = sys.stdin.read()
        else:
            candidates = sorted(
                p for p in resp_dir.iterdir() if p.is_file()
            )
            response_text = candidates[-1].read_text() if candidates else ""
        path = write_receipt(resp_dir, argv[3], response_text)
        print(f"receipt written: {path}")
        return 0
    if cmd == "score-workers":
        report = score_worker_responses()
        for condition, s in report["summary"].items():
            print(f"{condition}: {s['rate']}")
        print(f"report: {ROOT / 'runs' / 'report.json'}")
        return 0
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
