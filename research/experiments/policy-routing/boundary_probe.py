"""Post-collection MCP boundary diagnostic; never a coding-model trial."""

import asyncio
import importlib.util
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def probe(root, destination):
    root = root.resolve()
    runner = load(root / "snapshot/experiment/run.py", "probe_runner")
    runner.verify_bundle(root)
    rubric = load(root / "snapshot/experiment/rubric.py", "probe_rubric")
    destination.mkdir(exist_ok=False)
    token = uuid.uuid4().hex
    calls = [
        ("memory_search", {"repository": "payment-worker"}),
        ("memory_search", {"repository": "clearing-adapter"}),
        ("memory_get", {"assertion_id": "EA-ROUTE-OLD"}),
        ("memory_get", {"assertion_id": "EA-ROUTE-CURRENT"}),
        ("memory_get", {"assertion_id": "EA-ROUTE-PRIVATE"}),
        ("memory_get", {"assertion_id": "EA-NONEXISTENT"}),
    ]
    started = datetime.now(UTC).isoformat()
    records = []
    with (destination / "mcp.stderr").open("x") as errors:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(root / "snapshot/experiment/server.py")],
            env={**os.environ, "TRIAL_TOKEN": token, "PYTHONPATH": str(root / "snapshot/src")},
            cwd=str(destination.resolve()),
        )
        async with (
            stdio_client(params, errlog=errors) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            for name, arguments in calls:
                result = await session.call_tool(name, {**arguments, "token": token})
                records.append(
                    {
                        "at": datetime.now(UTC).isoformat(),
                        "name": name,
                        "arguments": arguments,
                        "response": result.model_dump(mode="json"),
                    }
                )
    payloads = [json.loads(r["response"]["content"][0]["text"]) for r in records[:4]]
    current = payloads[0]["assertions"][0]
    checks = {
        "current_only_not_historical_or_private": [a["id"] for a in payloads[0]["assertions"]]
        == ["EA-ROUTE-CURRENT"],
        "exception_only": [a["id"] for a in payloads[1]["assertions"]] == ["EA-ROUTE-EXCEPTION"],
        "historical_get_retains_status": payloads[2]["assertion"]["status"] == "superseded",
        "mixed_provenance_redacted_in_search_and_get": all(
            any(p["redacted"] for p in a["provenance"]) and a["rationale"] is None
            for a in (current, payloads[3]["assertion"])
        ),
        "denied_and_missing_errors_indistinguishable": records[4]["response"]["is_error"]
        and records[5]["response"]["is_error"]
        and records[4]["response"]["content"] == records[5]["response"]["content"],
        "no_restricted_response_markers": not rubric.leaks([r["response"] for r in records]),
    }
    runner.write_json(
        destination / "report.json",
        {
            "evidence_type": "post-collection operator-driven deterministic MCP diagnostic",
            "not_model_trials": True,
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(),
            "manifest_sha256": runner.digest(root / "manifest.json"),
            "probe_source_sha256": runner.digest(Path(__file__)),
            "mcp_stderr_sha256": runner.digest(destination / "mcp.stderr"),
            "records": records,
            "checks": checks,
            "pass": all(checks.values()),
        },
    )
    print(json.dumps(checks, indent=2))
    return all(checks.values())


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(probe(Path(sys.argv[1]), Path(sys.argv[2]))) else 1)
