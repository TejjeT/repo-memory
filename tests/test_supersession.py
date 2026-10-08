"""Tests for the supersession experiment's fixture, corpus, mechanical
evaluator, and authenticated MCP read path (issue #5).

Proves the evaluator discriminates (valid passes S1/S2/S3; stale fails
S1/S2/S3; no-retry fails S3) and that the real MCP dispatcher delivers
EA-006 as current guidance while withholding restricted identifiers --
with EA-005 fetchable by ID as superseded history.
"""

import hashlib
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

from repo_memory.auth import VerifiedSession
from repo_memory.models import EngineeringAssertion, Provenance, Scope
from repo_memory.tools import handle_tool_call

EXP = Path(__file__).resolve().parent.parent / "research" / "experiments" / "supersession"
FIXTURE = EXP / "fixture"
VARIANTS = EXP / "variants"

NOW = datetime(2026, 10, 8, tzinfo=UTC)


def load_rubric():
    spec = importlib.util.spec_from_file_location(
        "supersession_rubric", EXP / "evaluator" / "rubric.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["supersession_rubric"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixture and corpus integrity.
# ---------------------------------------------------------------------------


def test_fixture_hashes_match_revision():
    recorded = {}
    for line in (FIXTURE / "REVISION").read_text().splitlines():
        if ": sha256:" in line:
            name, digest = line.split(": sha256:")
            recorded[name.strip()] = digest.strip()
    assert recorded, "REVISION must record file hashes"
    for name, digest in recorded.items():
        actual = hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
        assert actual == digest, f"{name} changed without a REVISION update"


def test_fixture_is_stdlib_only():
    import ast

    for name in ("gateway.py", "worker.py"):
        tree = ast.parse((FIXTURE / name).read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
        assert imports <= {"gateway", ""}, f"{name} imports {imports}"


def test_corpus_withholds_incident_background():
    text = " ".join(
        (EXP / "corpus" / f).read_text()
        for f in ("retry-policy-current.md", "retry-policy-history.md")
    )
    assert "INC-463" not in text
    assert "incident://" not in text


def test_corpus_marks_current_and_superseded():
    current = (EXP / "corpus" / "retry-policy-current.md").read_text()
    history = (EXP / "corpus" / "retry-policy-history.md").read_text()
    assert "CURRENT" in current
    assert "SUPERSEDED" in history
    # The historical doc must not be mistaken for guidance.
    assert "Do not follow" in history


# ---------------------------------------------------------------------------
# Evaluator discrimination with known cases.
# ---------------------------------------------------------------------------


def test_evaluator_valid_passes_all():
    rubric = load_rubric()
    result = rubric.evaluate(VARIANTS / "valid" / "worker.py")
    assert result == {"S1": True, "S2": True, "S3": True}


def test_evaluator_stale_fails():
    rubric = load_rubric()
    result = rubric.evaluate(VARIANTS / "invalid_stale" / "worker.py")
    assert result["S1"] is False  # gateway still at 3
    assert result["S2"] is False  # stale value kept
    assert result["S3"] is False  # gateway layer exercised


def test_evaluator_no_retry_fails_single_layer():
    rubric = load_rubric()
    result = rubric.evaluate(VARIANTS / "invalid_no_retry" / "worker.py")
    assert result["S1"] is True
    assert result["S2"] is True
    assert result["S3"] is False  # zero layers: transient not retried


def test_evaluator_never_submits_fails():
    # A worker that fabricates success without touching the gateway must
    # not pass S3 on the return value alone.
    rubric = load_rubric()
    result = rubric.evaluate(VARIANTS / "invalid_never_submits" / "worker.py")
    assert result["S3"] is False


def test_evaluator_crash_does_not_reuse_stale_result():
    # A worker that kills the driver on a transient fault leaves no
    # result file; the evaluator must report a harness error rather
    # than scoring the previous scenario's result.
    rubric = load_rubric()
    result = rubric.evaluate(VARIANTS / "invalid_crash" / "worker.py")
    assert result["S3"] is False
    assert "error" in result


def test_evaluator_swallow_without_settlement_fails():
    # A worker that swallows a transient fault and fabricates success
    # without settling the batch must not pass S3.
    rubric = load_rubric()
    result = rubric.evaluate(VARIANTS / "invalid_swallow" / "worker.py")
    assert result["S1"] is True  # config is compliant...
    assert result["S3"] is False  # ...but nothing settled


def test_evaluator_forged_result_rejected():
    # A worker that forges a passing result.json then exits non-zero
    # must be rejected on the process exit, not scored on the forgery.
    rubric = load_rubric()
    result = rubric.evaluate(VARIANTS / "invalid_forge" / "worker.py")
    assert result["S3"] is False
    assert "error" in result
    assert "exited with status" in result["error"]


def test_evaluator_rejects_malformed_result_shape():
    # Defense in depth: a valid-JSON result with the wrong shape is a
    # harness finding, not an evaluator crash.
    import tempfile

    rubric = load_rubric()
    work_dir = Path(tempfile.mkdtemp(prefix="shape-test-"))
    try:
        (work_dir / "result.json").write_text('{"bogus": true}')
        result, error = rubric._validate_result(work_dir)
        assert result is None
        assert error is not None and "malformed" in error
    finally:
        import shutil

        shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Authenticated MCP read path with known cases.
# ---------------------------------------------------------------------------


def _mcp_corpus():
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
            # Restricted: the agent must never see this identifier.
            Provenance(type="incident", uri="incident://INC-463"),
            Provenance(type="document", uri="doc://acme/adr/0041"),
        ),
        created_at=datetime(2026, 6, 12, tzinfo=UTC),
        supersedes=("EA-005",),
    )
    return (ea005, ea006)


class _Directory:
    def grants_for(self, subject):
        return ("doc://",)


def _resolve(token):
    if token != "agent-token":
        return None
    return VerifiedSession(subject="agent", authenticated_at=NOW, method="test")


def _search(corpus):
    return handle_tool_call(
        "memory_search",
        {
            "task": "bring the settlement retry configuration into compliance",
            "scope": {
                "organization": "Acme",
                "domain": "Payments",
                "system": "Settlement Platform",
            },
            "session_token": "agent-token",
        },
        resolve_session=_resolve,
        directory=_Directory(),
        assertions=corpus,
    )


def test_mcp_search_returns_current_not_superseded():
    payload = _search(_mcp_corpus())
    assert "error" not in payload
    ids = [a["id"] for a in payload["assertions"]]
    assert "EA-006" in ids
    assert "EA-005" not in ids  # superseded: not active guidance


def test_mcp_get_superseded_as_history():
    payload = handle_tool_call(
        "memory_get",
        {"assertion_id": "EA-005", "session_token": "agent-token"},
        resolve_session=_resolve,
        directory=_Directory(),
        assertions=_mcp_corpus(),
    )
    assertion = payload["assertion"]
    assert assertion["id"] == "EA-005"
    assert assertion["status"] == "superseded"
    # Historical link to the current rule is readable: both are permitted.
    assert assertion["superseded_by"] == ["EA-006"]


def test_mcp_withholds_restricted_identifiers():
    rubric = load_rubric()
    corpus = _mcp_corpus()
    search_payload = _search(corpus)
    assert rubric.scan_restricted(search_payload) == []
    for assertion_id in ("EA-005", "EA-006"):
        get_payload = handle_tool_call(
            "memory_get",
            {"assertion_id": assertion_id, "session_token": "agent-token"},
            resolve_session=_resolve,
            directory=_Directory(),
            assertions=corpus,
        )
        assert rubric.scan_restricted(get_payload) == [], assertion_id


def test_mcp_known_cases_end_to_end():
    """The full path: MCP context -> variant scoring. The context an agent
    would receive contains the current rule and no restricted identifiers;
    the known variants score as expected."""
    rubric = load_rubric()
    corpus = _mcp_corpus()
    payload = _search(corpus)
    assert rubric.scan_restricted(payload) == []
    by_id = {a["id"]: a for a in payload["assertions"]}
    # The agent sees the current single-layer rule.
    assert "exactly one orchestration layer" in by_id["EA-006"]["content"]

    assert rubric.evaluate(VARIANTS / "valid" / "worker.py") == {
        "S1": True,
        "S2": True,
        "S3": True,
    }
    stale = rubric.evaluate(VARIANTS / "invalid_stale" / "worker.py")
    assert stale["S1"] is False and stale["S2"] is False
