"""Human review records: blind-first protocol fields, consistency and queue quotas."""

import pytest
from pydantic import ValidationError

from audit_distill.data.labeling import LabelReview, next_item, parse_lines


def review(**change: object) -> LabelReview:
    values: dict[str, object] = {
        "queue": "primary_test",
        "query_id": "q1",
        "input_sha256": "h",
        "reviewer": "Test Person",
        "reviewer_kind": "human",
        "reviewed_at": "2026-09-23T00:00:00+00:00",
        "initial_verdict": "ABSENT",
        "upstream_verdict": "PRESENT",
        "final_verdict": "PRESENT",
        "input_sufficient": True,
        "check_equivalent": True,
        "assumptions": [],
        "vulnerable_lines": [4],
        "evidence_references": ["labels.csv#1"],
        "rationale": "Call precedes the balance update.",
    }
    return LabelReview.model_validate(values | change)


def test_review_records_are_human_and_internally_consistent() -> None:
    assert review().accepted
    for change in [
        {"reviewer_kind": "assistant"},
        {"reviewer": " "},
        {"rationale": ""},
        {"evidence_references": []},
        {"input_sufficient": False},  # a decided label needs sufficient input
        {"check_equivalent": False},
        {"final_verdict": "ABSENT"},  # lines only for PRESENT
        {"vulnerable_lines": [0]},
        {"final_verdict": "NONE"},
    ]:
        with pytest.raises(ValidationError):
            review(**change)
    unknown = review(final_verdict="UNKNOWN", input_sufficient=False, vulnerable_lines=[])
    assert not unknown.accepted


def test_line_ranges_are_bounded() -> None:
    assert parse_lines("3-5, 9", 10) == [3, 4, 5, 9]
    assert parse_lines("", 10) == []
    for text in ["0", "9-11", "5-3"]:
        with pytest.raises(ValueError):
            parse_lines(text, 10)


def test_primary_queue_skips_a_polarity_once_its_quota_is_met() -> None:
    entries = [
        {"query_id": "p1", "presentation_order": 1, "polarity_queue": "PRESENT"},
        {"query_id": "p2", "presentation_order": 2, "polarity_queue": "PRESENT"},
        {"query_id": "a1", "presentation_order": 3, "polarity_queue": "ABSENT"},
    ]
    assert next_item("primary_test", entries, [], 1)["query_id"] == "p1"
    done = [review(query_id="p1")]
    assert next_item("primary_test", entries, done, 1)["query_id"] == "a1"
    # A correction counts toward its final polarity, and UNKNOWN never fills a quota.
    corrected = [review(query_id="p1", final_verdict="ABSENT", vulnerable_lines=[])]
    assert next_item("primary_test", entries, corrected, 1)["query_id"] == "p2"
    assert next_item("primary_test", entries, corrected + [review(query_id="p2")], 1) is None
    audit = [e | {"polarity_queue": None} for e in entries]
    assert (
        next_item("training_audit", audit, [review(queue="training_audit", query_id="p1")], 1)[
            "query_id"
        ]
        == "p2"
    )
