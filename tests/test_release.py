"""SPEC v2.2 release stage: eligibility, matched balancing, grouped split and queues."""

import random
from pathlib import Path

import pytest

from audit_distill.data.records import Assessment, CandidateQuery, Scope
from audit_distill.data.release import (
    ReleaseQuery,
    audit_queue,
    cap_group_queries,
    eligibility,
    grouped_split,
    load_release_config,
    matched_selection,
    pragma_minor,
    primary_queue,
)

CONFIG = load_release_config(Path("configs/release.yaml"))
LEVELS = CONFIG.match_levels


def rq(
    qid: str,
    verdict: str,
    group: str,
    *,
    collection: str = "SCRUBD-CD",
    scope: str = "FUNCTION",
    pragma: str = "0.4",
    partition: str | None = None,
) -> ReleaseQuery:
    return ReleaseQuery(
        query_id=qid,
        artifact_id=f"a-{qid}",
        group_id=group,
        code_identity_sha256=f"c-{qid}",
        model_input_sha256=f"m-{qid}",
        upstream_verdict=verdict,
        collection=collection,
        scope_kind=scope,
        scope_name="C.f()",
        scope_start_line=1,
        scope_end_line=2,
        pragma_minor=pragma,
        assessment_ids=[f"e-{qid}"],
        qualifying_assessment_ids=[f"e-{qid}"],
        partition=partition,
    )


def candidate(
    qid: str, verdict: str, evidence: list[str], role: str = "development"
) -> CandidateQuery:
    return CandidateQuery(
        query_id=qid,
        artifact_id="art",
        assessment_ids=evidence,
        code_identity_sha256="id",
        check_id="REENTRANCY",
        scope=Scope(
            kind="FILE",
            name="FILE",
            start_line=1,
            end_line=1,
            start_token=0,
            end_token=1,
            token_identity="t",
        ),
        native_verdicts=[verdict],
        proposed_verdict=verdict,
        role=role,
        original_collections=["x"],
        group_id="g",
        mechanical_status="PASS",
        issues=[],
        review_required=[],
        model_input_sha256="m",
    )


def assessment(aid: str, verdict: str, tier: str, issues: list[str] | None = None) -> Assessment:
    return Assessment(
        assessment_id=aid,
        artifact_id="art",
        annotation_path="labels.csv",
        annotation_sha256="h",
        native_id=aid,
        native_property="no_findings" if issues else "RE",
        native_verdict=verdict,
        native_scope_kind="FILE",
        native_scope="FILE",
        candidate_checks=["REENTRANCY"],
        evidence_tier=tier,
        evidence_reference="ref",
        issues=issues or [],
    )


def test_eligibility_keeps_only_reviewed_supported_development_labels() -> None:
    coverage = ["negative_coverage_review_required"]
    evidence = {
        "rev": assessment("rev", "PRESENT", "UPSTREAM_REVIEWED"),
        "tool": assessment("tool", "ABSENT", "UNVERIFIED"),
        "nf": assessment("nf", "ABSENT", "UPSTREAM_REVIEWED", coverage),
    }
    queries = [
        candidate("ok", "PRESENT", ["rev"]),
        candidate("tool", "ABSENT", ["tool"]),
        candidate("unknown", "UNKNOWN", ["rev"]),
        candidate("nf", "ABSENT", ["nf"]),
        candidate("ext", "PRESENT", ["rev"], role="smartbugs_external"),
    ]
    code = {"art": "pragma solidity ^0.4.24; contract C {}"}
    uncovered = CONFIG.model_copy(update={"coverage_confirmed_sources": {}})
    kept, excluded = eligibility(queries, evidence, {"art": "other"}, code, uncovered)
    assert [q.query_id for q in kept] == ["ok"]
    assert kept[0].pragma_minor == "0.4"
    assert {e["query_id"]: e["reason"] for e in excluded} == {
        "tool": "unverified_evidence_only",
        "unknown": "unknown_or_disputed",
        "nf": "negative_coverage_unconfirmed",
    }
    # A documented covering protocol admits the no-finding negative; external never enters.
    kept, _ = eligibility(queries, evidence, {"art": "salzano"}, code, CONFIG)
    assert [q.query_id for q in kept] == ["nf", "ok"]


def test_pragma_screen() -> None:
    assert pragma_minor("pragma solidity >=0.6.0 <0.8.0;") == "0.6"
    assert pragma_minor("contract C {}") == "unspecified"


def test_group_cap_is_per_polarity_and_order_independent() -> None:
    rows = [rq(f"p{i}", "PRESENT", "big") for i in range(5)] + [rq("a", "ABSENT", "big")]
    kept, dropped = cap_group_queries(rows, 3, 42)
    assert sum(q.upstream_verdict == "PRESENT" for q in kept) == 3
    assert [q.query_id for q in kept if q.upstream_verdict == "ABSENT"] == ["a"]
    assert {d["reason"] for d in dropped} == {"group_query_cap"}
    again, _ = cap_group_queries(list(reversed(rows)), 3, 42)
    assert again == kept


def test_matching_is_balanced_exact_first_and_order_independent() -> None:
    cases = [
        rq("p1", "PRESENT", "g1", collection="dappscan", pragma="0.7"),
        rq("p2", "PRESENT", "g2", collection="SCRUBD-CD", pragma="0.4"),
    ]
    controls = [
        rq("a1", "ABSENT", "g3", collection="SCRUBD-CD", pragma="0.4"),
        rq("a2", "ABSENT", "g4", collection="SCRUBD-CD", pragma="0.7"),
        rq("a3", "ABSENT", "g5", collection="SCRUBD-CD", pragma="0.4", scope="FILE"),
    ]
    selected, surplus = matched_selection(cases + controls, LEVELS, 42)
    pairs = {q.query_id: (q.match_partner, q.match_level) for q in selected}
    assert pairs["p2"] == ("a1", 0)  # same collection, scope and pragma
    assert pairs["p1"] == ("a2", 2)  # no dappscan control: same scope and pragma
    assert [s["query_id"] for s in surplus] == ["a3"]
    assert sum(q.upstream_verdict == "PRESENT" for q in selected) == 2
    assert sum(q.upstream_verdict == "ABSENT" for q in selected) == 2
    shuffled = cases + controls
    random.Random(1).shuffle(shuffled)
    assert matched_selection(shuffled, LEVELS, 42)[0] == selected


def test_matching_prefers_controls_from_unused_groups() -> None:
    rows = [rq("p1", "PRESENT", "g1"), rq("p2", "PRESENT", "g2")]
    rows += [rq("a1", "ABSENT", "same"), rq("a2", "ABSENT", "same"), rq("a3", "ABSENT", "other")]
    selected, _ = matched_selection(rows, LEVELS, 42)
    groups = {q.group_id for q in selected if q.upstream_verdict == "ABSENT"}
    assert groups == {"same", "other"}


def pool(groups_per_polarity: int) -> list[ReleaseQuery]:
    rows = []
    for i in range(groups_per_polarity):
        collection = "SCRUBD-CD" if i % 2 else "smartbugs_results"
        rows.append(rq(f"p{i:03}", "PRESENT", f"gp{i}", collection=collection))
        rows.append(rq(f"a{i:03}", "ABSENT", f"ga{i}", collection=collection))
        rows.append(rq(f"b{i:03}", "ABSENT", f"ga{i}", collection=collection, scope="FILE"))
    return rows


def test_split_is_group_disjoint_balanced_and_gated() -> None:
    selected, surplus, seed, attempts = grouped_split(pool(200), CONFIG)
    assert seed == attempts[-1]["seed"] and attempts[-1]["passed"]
    partition_of: dict[str, str] = {}
    for row in selected + [s for s in surplus]:
        group = row.group_id if isinstance(row, ReleaseQuery) else row["group_id"]
        part = row.partition if isinstance(row, ReleaseQuery) else row["partition"]
        assert partition_of.setdefault(group, part) == part
    for name in ("train", "validation", "heldout"):
        rows = [q for q in selected if q.partition == name]
        assert sum(q.upstream_verdict == "PRESENT" for q in rows) == sum(
            q.upstream_verdict == "ABSENT" for q in rows
        )
        # Every case's control sits in the same partition.
        partners = {q.query_id: q for q in rows}
        assert all(q.match_partner in partners for q in rows)
    with pytest.raises(ValueError, match="No split seed"):
        grouped_split(pool(40), CONFIG.model_copy(update={"split_seed_last": 43}))


def test_review_queues_are_deterministic_blind_and_group_unique() -> None:
    selected, _, _, _ = grouped_split(pool(200), CONFIG)
    train = [q for q in selected if q.partition == "train"]
    audit = audit_queue(train, CONFIG)
    by_query = {q.query_id: q for q in train}
    cells: dict[tuple[str, str], set[str]] = {}
    for row in audit:
        cell = (row["cell"]["collection"], row["cell"]["upstream_verdict"])
        cells.setdefault(cell, set()).add(by_query[row["query_id"]].group_id)
    assert all(len(groups) == CONFIG.audit_per_cell for groups in cells.values())
    assert sorted(r["presentation_order"] for r in audit) == list(range(1, len(audit) + 1))
    presented = [
        r["cell"]["upstream_verdict"] for r in sorted(audit, key=lambda r: r["presentation_order"])
    ]
    assert presented != sorted(presented) and presented != sorted(presented, reverse=True)
    heldout = [q for q in selected if q.partition == "heldout"]
    primary = primary_queue(heldout, CONFIG)
    assert primary == primary_queue(list(reversed(heldout)), CONFIG)
    for verdict in ("PRESENT", "ABSENT"):
        rows = [r for r in primary if r["polarity_queue"] == verdict]
        assert [r["polarity_order"] for r in rows] == list(range(1, len(rows) + 1))
        assert len({r["group_id"] for r in rows}) == len(rows)
