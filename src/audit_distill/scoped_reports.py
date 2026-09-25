"""Strict report contract: analysis, verdict and location, in a fixed field order.

Report-SFT writes the analysis before the verdict (`analysis_first`); the order
ablation trains on the same reports with the verdict first (`verdict_first`).
This module validates and serializes reports; it never generates them.
"""

import json
from collections.abc import Callable
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

Order = Literal["analysis_first", "verdict_first"]
ORDERS: dict[Order, tuple[str, str, str]] = {
    "analysis_first": ("analysis", "verdict", "location"),
    "verdict_first": ("verdict", "analysis", "location"),
}
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
    location: Location | None

    @model_validator(mode="after")
    def semantics(self, info: ValidationInfo) -> "ScopedReport":
        if (self.verdict == "PRESENT") != (self.location is not None):
            raise ValueError("PRESENT requires a location; ABSENT requires null")
        context = info.context or {}
        if self.location and "line_count" in context:
            if self.location.end_line > context["line_count"]:
                raise ValueError("Location exceeds supplied source line count")
        return self


def canonical_json(report: ScopedReport, order: Order) -> str:
    """Compact UTF-8 JSON in the condition's field order: the exact training target."""
    data = report.model_dump()
    return json.dumps(
        {key: data[key] for key in ORDERS[order]}, ensure_ascii=False, separators=(",", ":")
    )


def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """`json.loads` hook that rejects duplicate keys instead of keeping the last one."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_report(raw: str, *, line_count: int, order: Order) -> ScopedReport:
    """Strict parse of a model output; any deviation makes the prediction INVALID."""
    data = json.loads(raw, object_pairs_hook=unique_keys)
    if not isinstance(data, dict) or tuple(data) != ORDERS[order]:
        raise ValueError(f"Report fields must be exactly {ORDERS[order]} in that order")
    return ScopedReport.model_validate(data, context={"line_count": line_count})


def validate_teacher_report(
    payload: object,
    *,
    line_count: int,
    count_tokens: Callable[[str], int],
    max_tokens: int,
) -> ScopedReport:
    """Mechanical, label-blind check of a teacher report: schema, bounds and token budget.

    Use the pinned student tokenizer without special tokens. Never repair or truncate.
    The verdict is compared with the label only after this check passes.
    """
    report = ScopedReport.model_validate(payload, context={"line_count": line_count})
    tokens = count_tokens(canonical_json(report, "analysis_first"))
    if tokens > max_tokens:
        raise ValueError(f"Teacher report has {tokens} tokens; limit {max_tokens}")
    return report


ReasonCode = Literal["INSUFFICIENT_CONTEXT", "UNRESOLVED_ASSUMPTIONS"]


def teacher_schema() -> dict[str, object]:
    """Teacher answer schema, strict-mode compatible (all keys required, no extras).

    Key order is generation order: the teacher writes its analysis before the verdict.
    Length and line bounds are checked afterwards by `validate_teacher_report`.
    """

    def strict(properties: dict[str, object]) -> dict[str, object]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": list(properties),
            "properties": properties,
        }

    location = strict(
        {
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"},
            "function": {"type": ["string", "null"]},
        }
    )
    report = strict(
        {
            "analysis": {"type": "string"},
            "verdict": {"type": "string", "enum": ["PRESENT", "ABSENT"]},
            "location": {"anyOf": [{"type": "null"}, location]},
        }
    )
    return strict(
        {
            "status": {"type": "string", "enum": ["OK", "UNSUPPORTED"]},
            "report": {"anyOf": [{"type": "null"}, report]},
            "reason_code": {
                "anyOf": [{"type": "null"}, {"type": "string", "enum": list(get_args(ReasonCode))}]
            },
        }
    )


def report_schema() -> dict[str, object]:
    schema = ScopedReport.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["allOf"] = [
        {
            "if": {"properties": {"verdict": {"const": "ABSENT"}}},
            "then": {"properties": {"location": {"type": "null"}}},
            "else": {"properties": {"location": {"$ref": "#/$defs/Location"}}},
        }
    ]
    return schema
