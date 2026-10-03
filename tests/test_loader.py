from pathlib import Path

from repo_memory.loader import load_assertion

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "engineering-assertion.schema.json"


def test_load_incident_derived_assertion():
    assertion = load_assertion(
        ROOT / "examples" / "payments" / "idempotency-constraint.json",
        SCHEMA,
    )

    assert assertion.id == "EA-002"
    assert assertion.scope.system == "Settlement Platform"
    assert {target.id for target in assertion.applies_to} == {
        "payment-api",
        "settlement-engine",
        "payment-worker",
    }


def test_load_explicit_policy_exception():
    assertion = load_assertion(
        ROOT / "examples" / "payments" / "runtime-exception.json",
        SCHEMA,
    )

    assert assertion.id == "EA-003"
    assert assertion.type == "approved-exception"
    assert assertion.overrides == ("EA-001",)
