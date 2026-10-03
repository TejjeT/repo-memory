import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "spec" / "engineering-assertion.schema.json"
VALID_DIR = ROOT / "examples" / "payments"
INVALID_DIR = ROOT / "examples" / "invalid"


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


@pytest.mark.parametrize(
    "filename",
    [
        "runtime-policy.json",
        "idempotency-constraint.json",
        "runtime-exception.json",
        "superseded-retry-policy.json",
        "current-retry-policy.json",
    ],
)
def test_valid_examples_conform(validator: Draft202012Validator, filename: str):
    payload = json.loads((VALID_DIR / filename).read_text(encoding="utf-8"))

    validator.validate(payload)


@pytest.mark.parametrize(
    "filename",
    [
        "missing-scope.json",
        "missing-provenance.json",
    ],
)
def test_invalid_examples_fail_validation(
    validator: Draft202012Validator,
    filename: str,
):
    payload = json.loads((INVALID_DIR / filename).read_text(encoding="utf-8"))

    with pytest.raises(ValidationError):
        validator.validate(payload)
