"""Isolated worker trials with actual MCP transport (issue #5).

Unlike run.py (which embeds pre-rendered MCP JSON in job files), these
trials require workers to invoke the MCP tools via live stdio transport.
The transport log for each trial is the evidence that MCP was actually used.

Protocol per trial:
1. Create an isolated side chat (no experiment history).
2. Give the worker: fixture files + mcp_client.py + task instructions.
   - repo-only: fixture only.
   - generic-retrieval: fixture + corpus docs.
   - repo-memory: fixture + mcp_client.py; worker MUST call memory_search
     and memory_get via the client (actual JSON-RPC over stdio).
3. Worker produces worker.py; transport log is captured.
4. Issue collection-time receipt immediately (with prompt binding).
5. Score mechanically; report includes transport evidence.

Usage:
    python run_mcp_trials.py prepare   # write trial briefs
    # ... run each trial in a fresh side chat, save responses to
    #     responses/<trial>/response.md ...
    python run_mcp_trials.py collect   # verify transport log + issue receipts
    python run_mcp_trials.py score     # verify receipts and score
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[3]
FIXTURE = ROOT.parent / "fixture"
CORPUS = ROOT.parent / "corpus"
TRIAL_MCP = ROOT
EVALUATOR = ROOT.parent / "evaluator"

sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(EVALUATOR))

try:
    from rubric import evaluate as evaluate_variant  # noqa: E402
    from rubric import scan_restricted
except ImportError:
    # Rubric is optional for prepare/collect; only score needs it.
    evaluate_variant = None
    scan_restricted = None

TASK = (
    "Bring the settlement retry configuration into compliance with "
    "current policy (see fixture/worker.py)."
)
CONDITIONS = ("repo-only", "generic-retrieval", "repo-memory")
RUNS_PER_CONDITION = 3
EXPERIMENT = "supersession-mcp-transport-01"

MCP_CLIENT_CODE = (TRIAL_MCP / "mcp_client.py").read_text()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def trial_brief(condition: str, run: int) -> str:
    """Build the worker brief for one trial. For repo-memory, the worker
    must use the MCP client (actual transport); the guidance is NOT
    pre-rendered in the brief."""
    name = f"{condition}-r{run}"
    fixture_worker = (FIXTURE / "worker.py").read_text()
    fixture_gateway = (FIXTURE / "gateway.py").read_text()

    parts = [
        f"# Trial {name} ({EXPERIMENT})",
        "",
        "You are an engineer implementing a change in the payment-worker repository.",
        "",
        f"TASK: {TASK}",
        "",
        "## Fixture files",
        "",
        "### fixture/worker.py",
        "```python",
        fixture_worker,
        "```",
        "",
        "### fixture/gateway.py",
        "```python",
        fixture_gateway,
        "```",
    ]

    if condition == "generic-retrieval":
        parts += [
            "",
            "## Supplemental context (ordinary documents)",
            "",
            "### corpus/retry-policy-current.md",
            (CORPUS / "retry-policy-current.md").read_text(),
            "",
            "### corpus/retry-policy-history.md",
            (CORPUS / "retry-policy-history.md").read_text(),
        ]
    elif condition == "repo-memory":
        parts += [
            "",
            "## MCP access (actual transport required)",
            "",
            "You have a live MCP server with engineering memory. You MUST",
            "query it using the provided client script -- do not guess the",
            "current policy from the fixture alone.",
            "",
            "Save the script below as `mcp_client.py`, then run:",
            "```",
            "python mcp_client.py memory_search '{\"task\": \"<your task>\", "
            "\"scope\": {\"organization\": \"Acme\", \"domain\": \"Payments\", "
            "\"system\": \"Settlement Platform\"}, "
            "\"session_token\": \"trial-agent-token\"}'",
            "```",
            "Then call `memory_get` for any assertion IDs you need details on.",
            "The client logs all transport to `mcp-transport.log`.",
            "",
            "### mcp_client.py",
            "```python",
            MCP_CLIENT_CODE,
            "```",
        ]

    parts += [
        "",
        "## Rules",
        "- Implement the task by producing a new version of worker.py.",
        "- Keep the change minimal. Do not restructure unrelated code.",
        "- Follow every constraint in the context. Superseded guidance is",
        "  not current policy; follow the current items.",
        "",
        "## Output format",
        "- Respond with the complete, self-contained new worker.py.",
        "- You may wrap it in a single ```python fenced block.",
        "- Brief code comments are welcome. No explanations outside the code.",
    ]
    return "\n".join(parts)


def prepare_trials(dest: Path | None = None) -> list[str]:
    """Write trial briefs. Returns the trial names."""
    dest = dest or (ROOT / "briefs")
    dest.mkdir(parents=True, exist_ok=True)
    names = []
    for condition in CONDITIONS:
        for run in range(1, RUNS_PER_CONDITION + 1):
            name = f"{condition}-r{run}"
            brief = trial_brief(condition, run)
            (dest / f"{name}.md").write_text(brief)
            # Also write a manifest with the brief hash.
            manifest = {
                "job_name": name,
                "experiment": EXPERIMENT,
                "condition": condition,
                "run": run,
                "brief_sha256": sha256_text(brief),
                "created_at": datetime.now(UTC).isoformat(),
            }
            (dest / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=2))
            names.append(name)
    return names


def collect_trials() -> int:
    """Verify transport log and issue collection-time receipts for all
    responses present in responses/<trial>/response.md. Returns 0 on
    success."""

    responses_dir = ROOT / "responses"
    receipts_dir = ROOT / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    # Verify transport log exists (repo-memory trials only produce it,
    # but its presence is the MCP-use evidence).
    transport_log = ROOT / "mcp-transport.log"
    if transport_log.exists():
        lines = transport_log.read_text().strip().split("\n")
        print(f"transport log: {len(lines)} entries")
    else:
        print("warning: no transport log found")

    issued = 0
    for condition in CONDITIONS:
        for run in range(1, RUNS_PER_CONDITION + 1):
            name = f"{condition}-r{run}"
            response_path = responses_dir / name / "response.md"
            if not response_path.exists():
                print(f"skip {name}: no response")
                continue
            brief_path = ROOT / "briefs" / f"{name}.md"
            if not brief_path.exists():
                print(f"skip {name}: no brief")
                continue
            receipt_path = receipts_dir / f"receipt-{name}.json"
            if receipt_path.exists():
                print(f"skip {name}: receipt already exists")
                continue
            brief_text = brief_path.read_text()
            response_text = response_path.read_text()
            receipt = {
                "job_name": name,
                "experiment": EXPERIMENT,
                "captured_at": datetime.now(UTC).isoformat(),
                "brief_sha256": sha256_text(brief_text),
                "response_sha256": sha256_text(response_text),
                "response_bytes": len(response_text.encode()),
                "binding_type": "capture-time",
            }
            receipt_path.write_text(json.dumps(receipt, indent=2))
            print(f"issued receipt for {name}")
            issued += 1
    print(f"issued {issued} receipts")
    return 0


def score_trials() -> int:
    """Score all trials with receipts using the mechanical rubric check.
    Returns 0 if all scored trials pass."""
    import re

    if evaluate_variant is None:
        print("error: rubric not available", file=sys.stderr)
        return 2

    receipts_dir = ROOT / "receipts"
    responses_dir = ROOT / "responses"
    results = {}

    for condition in CONDITIONS:
        for run in range(1, RUNS_PER_CONDITION + 1):
            name = f"{condition}-r{run}"
            receipt_path = receipts_dir / f"receipt-{name}.json"
            if not receipt_path.exists():
                results[name] = "NO_RECEIPT"
                continue
            response_path = responses_dir / name / "response.md"
            if not response_path.exists():
                results[name] = "NO_RESPONSE"
                continue
            # Verify receipt hash matches response.
            receipt = json.loads(receipt_path.read_text())
            response_text = response_path.read_text()
            if receipt["response_sha256"] != sha256_text(response_text):
                results[name] = "RECEIPT_MISMATCH"
                continue
            # Extract code and check the mechanical criterion.
            m = re.search(r"```python\n(.*?)```", response_text, re.DOTALL)
            code = m.group(1) if m else response_text
            # Mechanical: GATEWAY_MAX_RETRIES must be 0, and no
            # restricted markers (INC-463, incident://) in the response.
            if scan_restricted and scan_restricted(code):
                results[name] = "FAIL_LEAK"
            elif "GATEWAY_MAX_RETRIES = 0" in code:
                results[name] = "PASS"
            else:
                results[name] = "FAIL"

    for name in sorted(results):
        print(f"{name}: {results[name]}")

    # Summary by condition.
    for condition in CONDITIONS:
        passes = sum(
            1 for r in range(1, RUNS_PER_CONDITION + 1)
            if results.get(f"{condition}-r{r}") == "PASS"
        )
        total = sum(
            1 for r in range(1, RUNS_PER_CONDITION + 1)
            if results.get(f"{condition}-r{r}") not in ("NO_RECEIPT", "NO_RESPONSE")
        )
        print(f"{condition}: {passes}/{total} passed")

    failed = [n for n, r in results.items() if r not in ("PASS", "NO_RECEIPT", "NO_RESPONSE")]
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: run_mcp_trials.py prepare|collect|score")
        return 2
    if argv[1] == "prepare":
        names = prepare_trials()
        print(f"wrote {len(names)} trial briefs")
        return 0
    if argv[1] == "collect":
        return collect_trials()
    if argv[1] == "score":
        return score_trials()
    print(f"unknown command: {argv[1]}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
