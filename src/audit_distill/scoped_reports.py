"""Strict SPEC v2.2 semantic report contract for the reentrancy-only experiment.

The analysis field comes first so greedy decoding writes the code-grounded analysis
before committing to a verdict. This module validates records; it never generates
explanations or invokes a model.
"""

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

Text = Annotated[str, Field(min_length=1, max_length=900, pattern=r"\S")]
Analysis = Annotated[str, Field(min_length=1, max_length=1200, pattern=r"\S")]


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    function: str | None

    @model_validator(mode="after")
    def ordered(self) -> "Location":
        if self.end_line < self.start_line:
            raise ValueError("Location end precedes start")
        return self


class ScopedReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    analysis: Analysis
    verdict: Literal["PRESENT", "ABSENT"]
    severity: Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    location: Location | None
    exploit_scenario: Text | None
    recommendation: Text | None

    @model_validator(mode="after")
    def semantics(self, info: ValidationInfo) -> "ScopedReport":
        if self.verdict == "ABSENT":
            if self.severity != "NONE" or any(
                value is not None
                for value in (self.location, self.exploit_scenario, self.recommendation)
            ):
                raise ValueError("ABSENT requires NONE severity and null positive-only fields")
        elif self.severity == "NONE" or any(
            value is None for value in (self.location, self.exploit_scenario, self.recommendation)
        ):
            raise ValueError("PRESENT requires positive severity, location, exploit and mitigation")
        context = info.context or {}
        if self.location and "line_count" in context:
            if self.location.end_line > context["line_count"]:
                raise ValueError("Location exceeds supplied source line count")
        if "verdict" in context and self.verdict != context["verdict"]:
            raise ValueError("Report differs from the known reference verdict")
        return self


def parse_report(raw: str, *, line_count: int) -> ScopedReport:
    def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return ScopedReport.model_validate(
        json.loads(raw, object_pairs_hook=unique_keys), context={"line_count": line_count}
    )


def report_schema() -> dict[str, object]:
    schema = ScopedReport.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    text = {"type": "string", "minLength": 1, "maxLength": 900, "pattern": r"\S"}
    schema["allOf"] = [
        {
            "if": {"properties": {"verdict": {"const": "ABSENT"}}},
            "then": {
                "properties": {
                    "severity": {"const": "NONE"},
                    "location": {"type": "null"},
                    "exploit_scenario": {"type": "null"},
                    "recommendation": {"type": "null"},
                }
            },
            "else": {
                "properties": {
                    "severity": {"enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                    "location": {"$ref": "#/$defs/Location"},
                    "exploit_scenario": text,
                    "recommendation": text,
                }
            },
        }
    ]
    return schema
