#!/usr/bin/env python3
"""Issue collection-time receipts for MCP transport trials.

Each receipt binds the trial brief hash to the response hash, issued
at collection time. This is the tamper-evident link for the new
experiment (supersession-mcp-transport-01).
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESPONSES = ROOT / "responses"
BRIEFS = ROOT / "briefs"
RECEIPTS = ROOT / "receipts"

EXPERIMENT = "supersession-mcp-transport-01"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def issue_receipt(trial_name: str) -> Path:
    """Issue a collection-time receipt for one trial."""
    brief_path = BRIEFS / f"{trial_name}.md"
    response_path = RESPONSES / trial_name / "response.md"
    
    if not brief_path.exists():
        raise FileNotFoundError(f"brief not found: {brief_path}")
    if not response_path.exists():
        raise FileNotFoundError(f"response not found: {response_path}")
    
    brief_text = brief_path.read_text()
    response_text = response_path.read_text()
    
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    receipt_path = RECEIPTS / f"receipt-{trial_name}.json"
    
    if receipt_path.exists():
        raise FileExistsError(f"receipt already exists for {trial_name}")
    
    receipt = {
        "job_name": trial_name,
        "experiment": EXPERIMENT,
        "captured_at": datetime.now(UTC).isoformat(),
        "brief_sha256": sha256_text(brief_text),
        "response_sha256": sha256_text(response_text),
        "response_bytes": len(response_text.encode()),
        "binding_type": "capture-time",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2))
    return receipt_path


def main(argv):
    trials = [
        "repo-only-r1", "repo-only-r2", "repo-only-r3",
        "generic-retrieval-r1", "generic-retrieval-r2", "generic-retrieval-r3",
        "repo-memory-r1", "repo-memory-r3",
        # repo-memory-r2 incomplete - no receipt
    ]
    for trial in trials:
        try:
            path = issue_receipt(trial)
            print(f"issued: {path.name}")
        except Exception as e:
            print(f"failed {trial}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
