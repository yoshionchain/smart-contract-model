import json

import jsonschema
import pytest
from pydantic import ValidationError

from audit_distill.scoped_reports import ScopedReport, parse_report, report_schema


@pytest.fixture
def positive() -> dict[str, object]:
    return {
        "analysis": "Fixture analysis.",
        "verdict": "PRESENT",
        "severity": "HIGH",
        "location": {"start_line": 2, "end_line": 3, "function": "withdraw"},
        "exploit_scenario": "Fixture consequence.",
        "recommendation": "Fixture mitigation.",
    }


def test_scoped_report_semantics_and_context(positive: dict[str, object]) -> None:
    schema = report_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(positive, schema)
    assert parse_report(json.dumps(positive), line_count=3).verdict == "PRESENT"
    with pytest.raises(ValidationError, match="line count"):
        parse_report(json.dumps(positive), line_count=2)
    with pytest.raises(ValidationError, match="reference verdict"):
        ScopedReport.model_validate(positive, context={"verdict": "ABSENT"})
    negative = positive | {
        "verdict": "ABSENT",
        "severity": "NONE",
        "location": None,
        "exploit_scenario": None,
        "recommendation": None,
    }
    jsonschema.validate(negative, schema)
    assert parse_report(json.dumps(negative), line_count=3).verdict == "ABSENT"
    with pytest.raises(ValidationError):
        ScopedReport.model_validate(negative | {"severity": "LOW"})


@pytest.mark.parametrize(
    "change",
    [
        {"verdict": "UNKNOWN"},
        {"verdict": "REENTRANCY"},
        {"severity": "NONE"},
        {"location": None},
        {"recommendation": None},
        {"analysis": " "},
        {"analysis": "x" * 1201},
        {"explanation": "Retired v2.1 field."},
        {"exploit_scenario": "x" * 901},
        {"vulnerability": "REENTRANCY"},
        {"location": {"start_line": True, "end_line": 3, "function": None}},
    ],
)
def test_report_schema_and_runtime_reject_invalid_fields(
    positive: dict[str, object], change: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        ScopedReport.model_validate(positive | change)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(positive | change, report_schema())


def test_duplicate_json_keys_and_reversed_locations(positive: dict[str, object]) -> None:
    raw = json.dumps(positive)
    with pytest.raises(ValueError, match="Duplicate"):
        parse_report('{"verdict": "ABSENT",' + raw[1:], line_count=3)
    with pytest.raises(ValueError):
        parse_report("```json\n" + raw + "\n```", line_count=3)
    with pytest.raises(ValidationError, match="precedes"):
        ScopedReport.model_validate(
            positive | {"location": {"start_line": 3, "end_line": 2, "function": None}}
        )


def test_analysis_precedes_verdict_in_canonical_order(positive: dict[str, object]) -> None:
    report = ScopedReport.model_validate(positive)
    assert list(json.loads(report.model_dump_json()))[:2] == ["analysis", "verdict"]
    assert list(report_schema()["properties"])[0] == "analysis"
    assert report_schema()["required"][:2] == ["analysis", "verdict"]
