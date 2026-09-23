"""Contextual teacher-target validation, independent of any generation backend."""

from collections.abc import Callable
from typing import Literal

from audit_distill.scoped_reports import ScopedReport


def validate_teacher_target(
    payload: dict[str, object],
    *,
    verdict: Literal["PRESENT", "ABSENT"],
    line_count: int,
    count_tokens: Callable[[str], int],
    max_tokens: int,
) -> ScopedReport:
    """Validate semantic fields and compact target length; never repair or truncate.

    Production callers must use the pinned student tokenizer without special
    tokens and the configured report budget. Batch IDs/wrappers are not targets.
    Isolation and batch-envelope validation belong to the future teacher runner.
    """
    report = ScopedReport.model_validate(
        payload, context={"verdict": verdict, "line_count": line_count}
    )
    tokens = count_tokens(report.model_dump_json())
    if tokens < 1 or tokens > max_tokens:
        raise ValueError(f"Teacher target has {tokens} tokens; expected 1..{max_tokens}")
    return report
