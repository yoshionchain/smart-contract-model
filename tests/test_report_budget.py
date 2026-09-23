import json
from pathlib import Path

import pytest

from audit_distill.data.settings import load_data_config
from audit_distill.reports import validate_teacher_target


def test_canonical_target_limit_includes_fields_and_never_truncates() -> None:
    payload = {
        "recommendation": "Fix café.",
        "exploit_scenario": "Lose funds.",
        "analysis": "Fixture re-entry analysis.",
        "location": {"function": None, "end_line": 2, "start_line": 1},
        "severity": "HIGH",
        "verdict": "PRESENT",
    }
    inputs: list[str] = []

    def count_tokens(text: str) -> int:
        inputs.append(text)
        return 480

    limit = load_data_config(Path("configs/project.yaml")).tokenizer.max_report_tokens
    report = validate_teacher_target(
        payload, verdict="PRESENT", line_count=2, count_tokens=count_tokens, max_tokens=limit
    )
    assert inputs == [report.model_dump_json()]
    assert list(json.loads(inputs[0])) == [
        "analysis",
        "verdict",
        "severity",
        "location",
        "exploit_scenario",
        "recommendation",
    ]
    assert '"recommendation":"Fix café."' in inputs[0]
    assert report.recommendation == payload["recommendation"]
    with pytest.raises(ValueError, match="481 tokens"):
        validate_teacher_target(
            payload, verdict="PRESENT", line_count=2, count_tokens=lambda _: 481, max_tokens=limit
        )
    with pytest.raises(ValueError, match="reference verdict"):
        validate_teacher_target(
            payload, verdict="ABSENT", line_count=2, count_tokens=count_tokens, max_tokens=limit
        )
