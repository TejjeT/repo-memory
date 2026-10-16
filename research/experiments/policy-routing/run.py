"""Freeze inputs, collect isolated JSONL worker processes, verify and score.

This module does not implement a model or certify filesystem isolation.
The supplied worker command must start a fresh, non-resumed model session.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONDITIONS = ("repo-only", "generic-retrieval", "repo-memory")
REPOSITORIES = ("payment-worker", "clearing-adapter", "reconciliation-worker")
EXPERIMENT = "policy-routing-v1"
TOOLS = [
    {"name": "memory_search", "arguments": {"repository": "string"}},
    {"name": "memory_get", "arguments": {"assertion_id": "string"}},
]


def now():
    return datetime.now(UTC).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def read_json(path):
    return json.loads(Path(path).read_text())


def command_files(command):
    return {
        part: digest(part) for part in command if Path(part).is_absolute() and Path(part).is_file()
    }


def job_content(snapshot, condition, trial_id):
    experiment = snapshot / "experiment"
    return {
        "trial_id": trial_id,
        "instructions": "Use only the supplied files/documents and listed tools. "
        "Do not inspect the study, evaluator, reference solutions or other trials. "
        "Start a fresh model session; do not resume any prior conversation. "
        "If tools are supplied, consult at least one before your terminal response.",
        "task": (experiment / "task.md").read_text(),
        "files": {p.name: p.read_text() for p in sorted((experiment / "fixture").glob("*.py"))},
        "documents": [] if condition == "repo-only" else [(experiment / "corpus.md").read_text()],
        "tools": TOOLS if condition == "repo-memory" else [],
        "output": "JSONL final: {type: final, code: complete policy.py, citations: [URI]}; "
        "or {type: abstain, reason: text, citations: []}. "
        "Tool request: {type: tool_call, name: tool, arguments: object}. "
        "Read one JSON reply after each tool request. No prose or Markdown.",
    }


def prepare(destination, command, model="unknown", *, timeout=180, turns=8, agent_config=None):
    """Create an exclusive bundle; never replace historical jobs or receipts."""
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(part, str) or not part for part in command)
    ):
        raise ValueError("worker command must be a non-empty JSON string array")
    if timeout <= 0 or turns < 1:
        raise ValueError("timeout and turn limit must be positive")
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=False)
    snapshot = root / "snapshot"
    shutil.copytree(
        HERE / "fixture",
        snapshot / "experiment/fixture",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for name in (
        "run.py",
        "server.py",
        "rubric.py",
        "task.md",
        "corpus.md",
        "assertions.json",
        "bridge.py",
    ):
        shutil.copyfile(HERE / name, snapshot / "experiment" / name)
    shutil.copytree(
        REPO / "src/repo_memory",
        snapshot / "src/repo_memory",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copytree(REPO / "spec", snapshot / "spec")
    # Validate the frozen assertion contract before generating any jobs.
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(read_json(snapshot / "spec/engineering-assertion.schema.json"))
    for assertion in read_json(snapshot / "experiment/assertions.json"):
        validator.validate(assertion)
    files = {
        str(p.relative_to(root)): digest(p) for p in sorted(snapshot.rglob("*")) if p.is_file()
    }
    jobs = {}
    for condition in CONDITIONS:
        for run in range(1, 4):
            name = f"{condition}-r{run}"
            directory = root / "trials" / name
            directory.mkdir(parents=True)
            job = job_content(snapshot, condition, str(uuid.uuid4()))
            write_json(directory / "job.json", job)
            jobs[name] = {
                "condition": condition,
                "trial_id": job["trial_id"],
                "job_sha256": digest(directory / "job.json"),
            }
    order = list(jobs)
    random.Random(20261016).shuffle(order)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True))
    manifest = {
        "experiment": EXPERIMENT,
        "created_at": now(),
        "files": files,
        "jobs": jobs,
        "order": order,
        "command": command,
        "command_file_hashes": command_files(command),
        "model_operator_reported": model,
        "model_version": "unknown unless worker reports it",
        "timeout_seconds": timeout,
        "max_tool_calls": turns,
        "git_revision": revision,
        "git_dirty": dirty,
        "python": sys.version,
        "mcp_version": importlib.metadata.version("mcp"),
        "isolation": "fresh process/workspace; no inherited chat supplied by runner; "
        "worker session freshness is operator-owned; filesystem is not sandboxed",
        "agent_config": agent_config,
    }
    write_json(root / "manifest.json", manifest)
    return root


def verify_bundle(root):
    manifest = read_json(root / "manifest.json")
    if (
        manifest.get("experiment") != EXPERIMENT
        or len(manifest.get("jobs", {})) != 9
        or len(manifest.get("order", [])) != 9
        or set(manifest.get("order", [])) != set(manifest["jobs"])
    ):
        raise ValueError("invalid study manifest")
    actual_files = {
        str(p.relative_to(root))
        for p in (root / "snapshot").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    if set(manifest["files"]) != actual_files:
        raise ValueError("incomplete snapshot manifest")
    for path, expected in manifest["files"].items():
        target = (root / path).resolve()
        if not target.is_relative_to(root.resolve()) or digest(target) != expected:
            raise ValueError(f"snapshot drift: {path}")
    if digest(HERE / "run.py") != manifest["files"]["snapshot/experiment/run.py"]:
        raise ValueError("run the frozen runner version for this bundle")
    for name, entry in manifest["jobs"].items():
        if name not in {f"{arm}-r{run}" for arm in CONDITIONS for run in range(1, 4)}:
            raise ValueError("invalid trial name")
        job_path = root / "trials" / name / "job.json"
        if digest(job_path) != entry["job_sha256"]:
            raise ValueError(f"job drift: {name}")
        if entry["condition"] != name.rsplit("-r", 1)[0] or read_json(job_path) != job_content(
            root / "snapshot", entry["condition"], entry["trial_id"]
        ):
            raise ValueError("trial payload differs from frozen inputs")
    return manifest


async def collect_trial(root, name):
    """Collection hook owns invocation, exact streams and the terminal receipt."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    manifest = verify_bundle(root)
    if command_files(manifest["command"]) != manifest["command_file_hashes"]:
        raise ValueError("worker command files changed before invocation")
    entry = manifest["jobs"][name]
    directory = root / "trials" / name
    job = read_json(directory / "job.json")
    workspace = directory / "workspace"
    workspace.mkdir(exist_ok=False)
    for filename, content in job["files"].items():
        if filename not in ("policy.py", "engine.py", "gateway.py"):
            raise ValueError("invalid workspace file")
        (workspace / filename).write_text(content)
    execution = str(uuid.uuid4())
    started, clock = now(), time.monotonic()
    final, status, process = None, "protocol_error", None
    calls = 0
    with (
        (directory / "worker.stdout").open("xb") as output,
        (directory / "worker.stdin").open("xb") as delivered,
        (directory / "worker.stderr").open("xb") as errors,
        (directory / "mcp.stderr").open("w") as mcp_errors,
        (directory / "transport.jsonl").open("x") as transport,
    ):

        def record(kind, payload):
            transport.write(
                json.dumps(
                    {
                        "trial_id": entry["trial_id"],
                        "execution_id": execution,
                        "at": now(),
                        "kind": kind,
                        "payload": payload,
                    }
                )
                + "\n"
            )
            transport.flush()

        async def send(payload):
            raw = (json.dumps(payload) + "\n").encode()
            delivered.write(raw)
            delivered.flush()
            process.stdin.write(raw)
            await process.stdin.drain()

        async with AsyncExitStack() as stack:
            session = None
            try:
                if entry["condition"] == "repo-memory":
                    token = uuid.uuid4().hex
                    env = {
                        **os.environ,
                        "TRIAL_TOKEN": token,
                        "PYTHONPATH": str(root / "snapshot/src"),
                    }
                    params = StdioServerParameters(
                        command=sys.executable,
                        args=[str(root / "snapshot/experiment/server.py")],
                        env=env,
                        cwd=str(workspace),
                    )
                    read, write = await stack.enter_async_context(
                        stdio_client(params, errlog=mcp_errors)
                    )
                    session = await stack.enter_async_context(ClientSession(read, write))
                    await asyncio.wait_for(session.initialize(), manifest["timeout_seconds"])
                process = await asyncio.create_subprocess_exec(
                    *manifest["command"],
                    cwd=workspace,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=errors,
                    limit=1024 * 1024,
                )
                write_json(
                    directory / "invocation.json",
                    {
                        "trial_id": entry["trial_id"],
                        "execution_id": execution,
                        "started_at": started,
                        "pid": process.pid,
                        "command": manifest["command"],
                        "command_file_hashes": manifest["command_file_hashes"],
                        "manifest_sha256": digest(root / "manifest.json"),
                        "job_sha256": entry["job_sha256"],
                        "workspace_at_launch": str(workspace),
                    },
                )
                await send(job)
                while True:
                    remaining = manifest["timeout_seconds"] - (time.monotonic() - clock)
                    raw = await asyncio.wait_for(process.stdout.readline(), max(remaining, 0.001))
                    if not raw:
                        break
                    output.write(raw)
                    output.flush()
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        raise ValueError("worker output must be an object")
                    if message.get("type") in ("final", "abstain"):
                        final = message
                        write_json(directory / "response.json", final)
                        process.stdin.close()
                        extra, _ = await asyncio.wait_for(
                            process.communicate(), max(remaining, 0.001)
                        )
                        output.write(extra)
                        if extra.strip():
                            raise ValueError("output after final response")
                        status = "completed" if process.returncode == 0 else "worker_failed"
                        break
                    if message.get("type") != "tool_call" or session is None:
                        raise ValueError("unauthorized or malformed tool call")
                    calls += 1
                    if calls > manifest["max_tool_calls"]:
                        raise ValueError("tool limit exceeded")
                    tool, arguments = message.get("name"), message.get("arguments")
                    valid_search = (
                        tool == "memory_search"
                        and isinstance(arguments, dict)
                        and set(arguments) == {"repository"}
                        and arguments["repository"] in REPOSITORIES
                    )
                    valid_get = (
                        tool == "memory_get"
                        and isinstance(arguments, dict)
                        and set(arguments) == {"assertion_id"}
                        and isinstance(arguments["assertion_id"], str)
                    )
                    if not (valid_search or valid_get):
                        raise ValueError("invalid memory request")
                    record("request", message)
                    result = await asyncio.wait_for(
                        session.call_tool(tool, {**arguments, "token": token}),
                        max(manifest["timeout_seconds"] - (time.monotonic() - clock), 0.001),
                    )
                    reply = {
                        "type": "tool_result",
                        "name": tool,
                        "result": json.loads(result.content[0].text),
                        "is_error": bool(result.is_error),
                    }
                    record("response", reply)
                    await send(reply)
            except TimeoutError:
                status = "timeout"
            except Exception as error:  # Record SDK/worker failures as assigned outcomes.
                record("failure", {"error": type(error).__name__, "message": str(error)})
            finally:
                if process is not None:
                    if process.returncode is None:
                        process.kill()
                    # Preserve buffered failure output as well as lines already read.
                    rest, _ = await asyncio.wait_for(process.communicate(), 5)
                    output.write(rest)
    # This runs at terminal collection, including failures, never as a later re-issue.
    required = ("worker.stdin", "worker.stdout", "worker.stderr", "mcp.stderr", "transport.jsonl")
    if (directory / "invocation.json").exists():
        required += ("invocation.json",)
    if final is not None:
        required += ("response.json",)
    if manifest.get("agent_config"):
        required += tuple(
            name for name in ("agent.json", "bridge.jsonl") if (directory / name).exists()
        )
    write_json(
        directory / "receipt.json",
        {
            "trial_id": entry["trial_id"],
            "execution_id": execution,
            "binding_type": "collection-hook",
            "started_at": started,
            "captured_at": now(),
            "elapsed_seconds": time.monotonic() - clock,
            "status": status,
            "manifest_sha256": digest(root / "manifest.json"),
            "job_sha256": entry["job_sha256"],
            "files": {path: digest(directory / path) for path in required},
            "tool_calls": calls,
            "returncode": process.returncode if process else None,
        },
    )
    return status


def load_rubric(root):
    spec = importlib.util.spec_from_file_location(
        "routing_rubric", root / "snapshot/experiment/rubric.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score(root):
    manifest = verify_bundle(root)
    rubric = load_rubric(root)
    results = {}
    for name, entry in manifest["jobs"].items():
        directory = root / "trials" / name
        row = {
            "condition": entry["condition"],
            "completed": False,
            "pass": False,
            "status": "not_run",
        }
        results[name] = row
        if not (directory / "receipt.json").exists():
            if (directory / "workspace").exists():
                row["status"] = "incomplete_collection"
            continue
        try:
            receipt = read_json(directory / "receipt.json")
            if (
                receipt["trial_id"] != entry["trial_id"]
                or receipt["binding_type"] != "collection-hook"
                or receipt["manifest_sha256"] != digest(root / "manifest.json")
                or receipt["job_sha256"] != entry["job_sha256"]
            ):
                raise ValueError("receipt binding mismatch")
            required = {
                "worker.stdin",
                "worker.stdout",
                "worker.stderr",
                "mcp.stderr",
                "transport.jsonl",
            }
            optional = {"response.json", "invocation.json"}
            if manifest.get("agent_config"):
                optional |= {"agent.json", "bridge.jsonl"}
            required |= {path for path in optional if (directory / path).exists()}
            if required != set(receipt["files"]):
                raise ValueError("incomplete receipt")
            for path, expected in receipt["files"].items():
                if Path(path).name != path or digest(directory / path) != expected:
                    raise ValueError("collected artifact drift")
            elapsed = receipt["elapsed_seconds"]
            if (
                type(elapsed) not in (int, float)
                or not math.isfinite(elapsed)
                or elapsed < 0
                or datetime.fromisoformat(receipt["captured_at"])
                < datetime.fromisoformat(receipt["started_at"])
            ):
                raise ValueError("invalid collection timing")
            if receipt["status"] not in {"completed", "protocol_error", "timeout", "worker_failed"}:
                raise ValueError("invalid terminal status")
            row.update(
                status=receipt["status"], elapsed_seconds=elapsed, tool_calls=receipt["tool_calls"]
            )
            trace = [
                json.loads(line)
                for line in (directory / "transport.jsonl").read_text().splitlines()
            ]
            if any(
                event["trial_id"] != entry["trial_id"]
                or event["execution_id"] != receipt["execution_id"]
                for event in trace
            ):
                raise ValueError("transport identity mismatch")
            start = datetime.fromisoformat(receipt["started_at"])
            end = datetime.fromisoformat(receipt["captured_at"])
            if any(not start <= datetime.fromisoformat(event["at"]) <= end for event in trace):
                raise ValueError("transport outside invocation window")
            exposed = {
                "job": read_json(directory / "job.json"),
                "transport": trace,
                "raw": (directory / "worker.stdout").read_text(),
                "delivered": (directory / "worker.stdin").read_text(),
            }
            row["restricted_markers"] = rubric.leaks(exposed)
            if receipt["status"] != "completed":
                continue
            if not {"response.json", "invocation.json"} <= set(receipt["files"]):
                raise ValueError("missing completion evidence")
            invocation = read_json(directory / "invocation.json")
            if (
                invocation["execution_id"] != receipt["execution_id"]
                or invocation["trial_id"] != entry["trial_id"]
                or invocation["job_sha256"] != entry["job_sha256"]
                or invocation["manifest_sha256"] != receipt["manifest_sha256"]
                or invocation["command"] != manifest["command"]
                or invocation["command_file_hashes"] != manifest["command_file_hashes"]
                or invocation["started_at"] != receipt["started_at"]
                or type(invocation["pid"]) is not int
                or invocation["pid"] <= 0
            ):
                raise ValueError("invocation identity mismatch")
            final = read_json(directory / "response.json")
            raw_messages = (directory / "worker.stdout").read_bytes().splitlines(keepends=True)
            messages = [json.loads(line) for line in raw_messages]
            if not messages or messages[-1] != final or receipt["returncode"] != 0:
                raise ValueError("response does not match terminal worker output")
            if manifest.get("agent_config"):
                if not {"agent.json", "bridge.jsonl"} <= set(receipt["files"]):
                    raise ValueError("missing built-in worker evidence")
                agent = read_json(directory / "agent.json")
                config = manifest["agent_config"]
                expected_message = config["message_template"].replace(
                    "{channel}", invocation["workspace_at_launch"] + "/agent-channel"
                )
                if (
                    agent["trial_id"] != entry["trial_id"]
                    or agent["execution_id"] != receipt["execution_id"]
                    or agent["request"]["fork_turns"] != "none"
                    or agent["request"]["model"] != config["model"]
                    or agent["request"]["message"] != expected_message
                    or not isinstance(agent["agent_id"], str)
                    or not agent["agent_id"]
                ):
                    raise ValueError("built-in worker identity/configuration mismatch")
                audit = [
                    json.loads(line)
                    for line in (directory / "bridge.jsonl").read_text().splitlines()
                ]
                if len(audit) != len(messages) or any(
                    event["index"] != index
                    or event["trial_id"] != entry["trial_id"]
                    or event["agent_id"] != agent["agent_id"]
                    or not start <= datetime.fromisoformat(event["at"]) <= end
                    or event["response_sha256"] != hashlib.sha256(raw).hexdigest()
                    for index, (event, raw) in enumerate(zip(audit, raw_messages, strict=True))
                ):
                    raise ValueError("bridge message binding mismatch")
                row["agent_id"] = agent["agent_id"]
                row["requested_model"] = agent["request"]["model"]
                row["requested_fork_turns"] = agent["request"]["fork_turns"]
            exchanges = [event for event in trace if event["kind"] in ("request", "response")]
            count = receipt["tool_calls"]
            if (
                type(count) is not int
                or not 0 <= count <= manifest["max_tool_calls"]
                or [e["kind"] for e in exchanges] != ["request", "response"] * count
                or [e["payload"] for e in exchanges[::2]]
                != [m for m in messages[:-1] if m.get("type") == "tool_call"]
            ):
                raise ValueError("transport does not match worker tool requests")
            delivery = [
                json.loads(line) for line in (directory / "worker.stdin").read_text().splitlines()
            ]
            if delivery != [read_json(directory / "job.json")] + [
                e["payload"] for e in exchanges[1::2]
            ]:
                raise ValueError("delivered tool responses do not match transport")
            row["delivered_bytes"] = (directory / "worker.stdin").stat().st_size
            row["worker_reported_metadata"] = final.get("metadata", {})
            row["abstained"] = final.get("type") == "abstain"
            citations = final.get("citations")
            if not isinstance(citations, list) or any(not isinstance(c, str) for c in citations):
                raise ValueError("malformed citations")
            if row["abstained"]:
                if not isinstance(final.get("reason"), str) or not final["reason"].strip():
                    raise ValueError("missing abstention reason")
                row["completed"] = True
                continue
            if final.get("type") != "final" or not isinstance(final.get("code"), str):
                raise ValueError("malformed final response")
            row["completed"] = True
            # Source labels must be available to this trial, not merely plausible.
            permitted = set()
            if entry["condition"] != "repo-only":
                permitted = {
                    "doc://payments/retry-2025",
                    "doc://payments/retry-2026",
                    "doc://payments/clearing-exception",
                    "doc://analytics/retry",
                }
            exposed_assertions = set()
            for event in trace:
                if event["kind"] == "response":
                    payload = event["payload"]["result"]
                    assertions = payload.get("assertions", [payload.get("assertion")])
                    exposed_assertions.update(a["id"] for a in assertions if a)
            permitted.update(exposed_assertions)
            if not set(citations) <= permitted:
                raise ValueError("undelivered citation")
            memory_used = any(
                event["kind"] == "response" and not event["payload"]["is_error"] for event in trace
            )
            row["outcome"] = rubric.evaluate(final["code"])
            row["pass"] = (
                row["outcome"]["pass"]
                and not row["restricted_markers"]
                and (entry["condition"] != "repo-memory" or memory_used)
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            row.update(status="invalid_evidence", error=str(error))
            row["pass"] = False
    summary = {}
    for arm in CONDITIONS:
        rows = [r for r in results.values() if r["condition"] == arm]
        summary[arm] = {
            "assigned": 3,
            "completed": sum(r["completed"] for r in rows),
            "passed": sum(r["pass"] for r in rows),
        }
    return {
        "experiment": EXPERIMENT,
        "results": results,
        "summary": summary,
        "model_operator_reported": manifest["model_operator_reported"],
        "interpretation": "Exploratory only; includes incomplete/failed assigned trials. "
        "Hashes verify artifacts, not independent execution or model identity.",
        "evidence_type": "command-collection; model identity is operator/worker-reported",
        "usage_and_cost": "unknown unless supplied in worker_reported_metadata",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "score"))
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--worker-command", help="JSON argv; fresh JSONL worker protocol")
    parser.add_argument("--model", default="unknown")
    args = parser.parse_args()
    if args.action == "prepare":
        if not args.worker_command:
            parser.error("prepare requires --worker-command")
        prepare(args.bundle, json.loads(args.worker_command), args.model)
    elif args.action == "run":
        manifest = verify_bundle(args.bundle)
        for name in manifest["order"]:
            if not (args.bundle / "trials" / name / "receipt.json").exists():
                print(name, asyncio.run(collect_trial(args.bundle.resolve(), name)), flush=True)
    else:
        report = score(args.bundle.resolve())
        print(json.dumps(report, indent=2))
        return 0 if all(r["passed"] == 3 for r in report["summary"].values()) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
