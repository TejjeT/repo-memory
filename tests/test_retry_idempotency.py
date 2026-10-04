"""Tests for the retry/idempotency experiment's fixture, corpus, and
mechanical evaluator (issue #5).

These tests prove the evaluator discriminates: the reference patch passes
all five rubric checks, while each known-invalid patch fails exactly the
checks its bug violates -- even though every variant imports cleanly and
settles the happy path (compilation/test success alone is insufficient).
"""

import hashlib
import importlib.util
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent / "research" / "experiments" / "retry-idempotency"
FIXTURE = EXP / "fixture"
VARIANTS = EXP / "variants"


def load_rubric():
    spec = importlib.util.spec_from_file_location(
        "retry_rubric", EXP / "evaluator" / "rubric.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["retry_rubric"] = module
    spec.loader.exec_module(module)
    return module


def test_fixture_hashes_match_revision():
    recorded = {}
    for line in (FIXTURE / "REVISION").read_text().splitlines():
        if line.startswith("- ") and ":" in line:
            name, digest = line[2:].split(":")
            recorded[name.strip()] = digest.strip()
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
    # Only the two retrievable documents are scanned: SOURCES.md is
    # evaluator documentation and names the withheld items explicitly.
    text = " ".join(
        (EXP / "corpus" / f).read_text()
        for f in ("retry-policy.md", "idempotency-guide.md")
    )
    for token in ("INC-412", "INC-463", "ADR-37", "ADR-41"):
        assert token not in text, f"restricted background leaked: {token}"
    withheld = (EXP / "corpus" / "SOURCES.md").read_text()
    assert "Withheld in all arms" in withheld


def test_corpus_states_both_rules():
    retry = (EXP / "corpus" / "retry-policy.md").read_text()
    assert "exactly one" in retry and "must stay disabled" in retry
    idem = (EXP / "corpus" / "idempotency-guide.md").read_text()
    assert "once per settlement batch" in idem or "Generate the key" in idem


def test_reference_passes_all_checks():
    rubric = load_rubric()
    result = rubric.score_variant(VARIANTS / "reference-worker.py")
    assert all(result["checks"].values()), result["detail"]


def test_regenerated_key_fails_r1_and_r2():
    rubric = load_rubric()
    result = rubric.score_variant(VARIANTS / "invalid-regenerated-key-worker.py")
    assert not result["checks"]["R1_key_stable"]
    assert not result["checks"]["R2_no_duplicate"]
    assert result["checks"]["R3_transient_retried"]
    assert result["checks"]["R4_permanent_stops"]
    assert result["checks"]["R5_single_retry_layer"]


def test_duplicate_layer_fails_r5_only():
    rubric = load_rubric()
    result = rubric.score_variant(VARIANTS / "invalid-duplicate-layer-worker.py")
    assert not result["checks"]["R5_single_retry_layer"]
    assert all(
        v for k, v in result["checks"].items() if k != "R5_single_retry_layer"
    ), result["detail"]


def test_unsafe_resubmit_fails_r1_and_r2():
    rubric = load_rubric()
    result = rubric.score_variant(VARIANTS / "invalid-unsafe-resubmit-worker.py")
    assert not result["checks"]["R1_key_stable"]
    assert not result["checks"]["R2_no_duplicate"]


def test_invalid_variants_still_import_and_settle_happy_path():
    """Compilation and happy-path success alone must not pass the rubric:
    every invalid variant imports cleanly, yet each fails its checks."""
    import py_compile

    rubric = load_rubric()
    one = [{"batch_id": "batch-1", "key": "key-1"}]
    for name in (
        "invalid-regenerated-key-worker.py",
        "invalid-duplicate-layer-worker.py",
        "invalid-unsafe-resubmit-worker.py",
        "invalid-swallowed-ambiguous-worker.py",
        "invalid-raise-on-success-worker.py",
        "invalid-hardcoded-key-worker.py",
    ):
        path = VARIANTS / name
        py_compile.compile(str(path), doraise=True)
        work_dir = rubric.apply_variant(path)
        try:
            run = rubric.run_scenario(work_dir, ["ok"], one)
        finally:
            import shutil

            shutil.rmtree(work_dir, ignore_errors=True)
        if name == "invalid-raise-on-success-worker.py":
            # This one fails even the happy path -- that is its bug.
            assert run["batch_results"][0]["raised"] == "PermanentError"
        else:
            assert run["batch_results"][0]["raised"] is None, (
                f"{name} fails even the happy path"
            )
        result = rubric.score_variant(path)
        assert not all(result["checks"].values()), f"{name} unexpectedly passes"


def test_swallowed_ambiguous_fails_r2_only():
    """Returning None on the response-lost failure keeps the settlement
    count right but swallows the failure: R2 must fail."""
    rubric = load_rubric()
    result = rubric.score_variant(
        VARIANTS / "invalid-swallowed-ambiguous-worker.py"
    )
    assert not result["checks"]["R2_no_duplicate"]
    assert all(
        v for k, v in result["checks"].items() if k != "R2_no_duplicate"
    ), result["detail"]


def test_raise_on_success_fails_r2_and_r3():
    """Raising PermanentError after a successful submit breaks clean and
    retried completions."""
    rubric = load_rubric()
    result = rubric.score_variant(
        VARIANTS / "invalid-raise-on-success-worker.py"
    )
    assert not result["checks"]["R2_no_duplicate"]
    assert not result["checks"]["R3_transient_retried"]
    assert result["checks"]["R1_key_stable"]
    assert result["checks"]["R4_permanent_stops"]
    assert result["checks"]["R5_single_retry_layer"]


def test_hardcoded_key_fails_r1_only():
    """A literal key is invisible to single-batch scenarios; the two-batch
    scenario must catch it."""
    rubric = load_rubric()
    result = rubric.score_variant(VARIANTS / "invalid-hardcoded-key-worker.py")
    assert not result["checks"]["R1_key_stable"]
    assert all(
        v for k, v in result["checks"].items() if k != "R1_key_stable"
    ), result["detail"]


def test_logging_worker_still_passes():
    """Ordinary debug output on stdout must not corrupt scoring: the
    result travels through the result file, not stdout."""
    rubric = load_rubric()
    result = rubric.score_variant(VARIANTS / "reference-logging-worker.py")
    assert all(result["checks"].values()), result["detail"]


def test_malformed_result_is_recorded_not_raised():
    """A missing result file becomes a harness failure in the report,
    never an exception escaping score_variant."""
    import shutil

    rubric = load_rubric()
    work_dir = rubric.apply_variant(VARIANTS / "reference-worker.py")
    try:
        # Poison the driver so no result file is written.
        (work_dir / "driver.py").write_text("import sys; sys.exit(0)\n")
        result = rubric.run_scenario(
            work_dir, ["ok"], [{"batch_id": "batch-1", "key": "key-1"}]
        )
        assert result.get("harness_error"), result
        scored = rubric.score_variant(VARIANTS / "reference-worker.py")
        # Sanity: the real driver still scores fine (poisoning was local).
        assert all(scored["checks"].values())
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_starting_fixture_has_no_retry():
    """The frozen starting point really is the pre-task code: no retry loop."""
    import ast

    tree = ast.parse((FIXTURE / "worker.py").read_text())
    loops = [
        n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))
    ]
    assert not loops, "starting worker.py already contains a retry loop"
