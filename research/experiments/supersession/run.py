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
    resp_dir: Path, job_name: str, response_text: str, dest: Path | None = None
) -> Path:
    """Issue a capture-time receipt for one worker response. The receipt
    hashes the exact response bytes and records when it was captured;
    it is the tamper-evident link between collection and scoring."""
    dest = dest or (ROOT / "runs" / "receipts")
    dest.mkdir(parents=True, exist_ok=True)
    captured_at = datetime.now(UTC).isoformat()
    receipt = {
        "job_name": job_name,
        "experiment": EXPERIMENT,
        "captured_at": captured_at,
        "response_sha256": sha256_text(response_text),
        "response_bytes": len(response_text.encode()),
        "response_path": str(resp_dir),
    }
    path = dest / receipt_name(job_name)
    path.write_text(json.dumps(receipt, indent=2))
    return path


def verify_receipt(
    resp_dir: Path, job_name: str, dest: Path | None = None
) -> tuple[bool, str]:
    """Re-hash the stored response and compare with the receipt. Returns
    (ok, message)."""
    dest = dest or (ROOT / "runs" / "receipts")
    receipt_path = dest / receipt_name(job_name)
    if not receipt_path.exists():
        return False, "missing receipt"
    receipt = json.loads(receipt_path.read_text())
    # Find the response file in resp_dir (first .md or .txt or raw file).
    candidates = sorted(
        p for p in resp_dir.iterdir() if p.is_file() and p.suffix in (".md", ".txt", ".py")
    )
    if not candidates:
        # Fall back: any single file.
        candidates = sorted(p for p in resp_dir.iterdir() if p.is_file())
    if not candidates:
        return False, "no response file"
    text = candidates[0].read_text()
    actual = sha256_text(text)
    if actual != receipt["response_sha256"]:
        return False, f"hash drift: receipt {receipt['response_sha256'][:12]} vs {actual[:12]}"
    return True, "ok"


def extract_worker_py(raw: str) -> tuple[str, str]:
    """Extract the worker.py from a raw worker response. Returns
    (code, method): method is 'fenced' or 'raw'."""
    m = re.search(r"```python\n(.*?)```", raw, re.DOTALL)
    if m:
        return m.group(1), "fenced"
    return raw, "raw"


def score_worker_responses(
    resp_root: Path | None = None, dest: Path | None = None
) -> dict:
    """Mechanically score every collected worker response. Returns the
    report dict and writes it to runs/report.json."""
    resp_root = resp_root or (ROOT / "runs" / "worker-responses")
    manifest = input_manifest()
    results: dict[str, dict] = {}
    for condition in CONDITIONS:
        for run in range(1, RUNS_PER_CONDITION + 1):
            name = f"{condition}-r{run}"
            resp_dir = resp_root / name
            entry: dict = {"job_name": name, "condition": condition, "run": run}
            ok, msg = verify_receipt(resp_dir, name)
            entry["receipt"] = {"ok": ok, "message": msg}
            if not ok:
                entry["scores"] = None
                results[name] = entry
                continue
            candidates = sorted(
                p
                for p in resp_dir.iterdir()
                if p.is_file() and p.suffix in (".md", ".txt", ".py")
            ) or sorted(p for p in resp_dir.iterdir() if p.is_file())
            raw = candidates[0].read_text()
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
            # S1+S2+S3 all true => pass.
            entry["pass"] = (
                isinstance(scores, dict)
                and scores.get("S1") is True
                and scores.get("S2") is True
                and scores.get("S3") is True
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
        print("usage: run.py prepare-workers | record-receipt <resp_dir> <job-name> | score-workers")
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
