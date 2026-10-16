"""JSONL-to-mailbox adapter for a parent-orchestrated fresh built-in worker.

The bridge never generates a solution or spawns a model. The parent supplies
the observed spawn record; the worker supplies each outgoing JSON message.
"""

import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def atomic_json(path, value):
    """Publish once, after all bytes exist; readers never observe partial JSON."""
    temporary = path.with_suffix(".pending")
    with temporary.open("x") as stream:
        json.dump(value, stream)
        stream.write("\n")
    if path.exists():
        raise FileExistsError(path)
    temporary.rename(path)


def main():
    workspace = Path.cwd()
    channel = workspace / "agent-channel"
    channel.mkdir(exist_ok=False)
    job = json.loads(sys.stdin.readline())
    atomic_json(channel / "in-000.json", job)
    # Registration is a parent-observed spawn response, not a worker claim.
    registration = workspace.parent / "agent.json"
    while not registration.exists():
        time.sleep(0.05)
    agent = json.loads(registration.read_text())
    if agent["trial_id"] != job["trial_id"]:
        raise ValueError("wrong trial registration")
    with (workspace.parent / "bridge.jsonl").open("x") as audit:
        for index in range(9):
            output = channel / f"out-{index:03d}.json"
            while not output.exists():
                time.sleep(0.05)
            raw = output.read_bytes()
            message = json.loads(raw)
            if not isinstance(message, dict):
                raise ValueError("worker message must be an object")
            forwarded = raw if raw.endswith(b"\n") else raw + b"\n"
            audit.write(
                json.dumps(
                    {
                        "at": datetime.now(UTC).isoformat(),
                        "index": index,
                        "agent_id": agent["agent_id"],
                        "trial_id": job["trial_id"],
                        "response_sha256": hashlib.sha256(forwarded).hexdigest(),
                    }
                )
                + "\n"
            )
            audit.flush()
            # Forward exact worker file bytes, adding only a missing JSONL newline.
            sys.stdout.buffer.write(forwarded)
            sys.stdout.buffer.flush()
            if message.get("type") in ("final", "abstain"):
                return 0
            reply = sys.stdin.readline()
            if not reply:
                return 1
            atomic_json(channel / f"in-{index + 1:03d}.json", json.loads(reply))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
