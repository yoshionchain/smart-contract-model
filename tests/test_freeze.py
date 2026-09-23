"""Freeze applies recorded human decisions exactly and fails on incomplete review."""

import pytest

from audit_distill.data.freeze import audit_outcome, primary_outcome
from audit_distill.data.ledger import Ledger
from audit_distill.data.release import ReleaseQuery
from tests.test_labeling import review
from tests.test_release import rq


def pair(case: str, control: str, group: str, collection: str = "SCRUBD-CD") -> list[ReleaseQuery]:
    return [
        rq(case, "PRESENT", f"{group}p", collection=collection).model_copy(
            update={"match_role": "case", "match_partner": control, "match_level": 0}
        ),
        rq(control, "ABSENT", f"{group}a", collection=collection).model_copy(
            update={"match_role": "control", "match_partner": case, "match_level": 0}
        ),
    ]


def audit_entry(query: ReleaseQuery) -> dict[str, object]:
    return {
        "query_id": query.query_id,
        "cell": {"collection": query.collection, "upstream_verdict": query.upstream_verdict},
    }


def audited(query: ReleaseQuery, final: str) -> object:
    return review(
        queue="training_audit",
        query_id=query.query_id,
        upstream_verdict=query.upstream_verdict,
        final_verdict=final,
        vulnerable_lines=[],
        input_sufficient=final != "UNKNOWN",
    )


def test_audit_errors_remove_pairs_and_systematic_cells_need_a_decision() -> None:
    rows = pair("p1", "a1", "g1") + pair("p2", "a2", "g2") + pair("p3", "a3", "g3", "dappscan")
    queries = {q.query_id: q for q in rows}
    entries = [audit_entry(queries[q]) for q in ["p1", "p2", "a1"]]
    with pytest.raises(ValueError, match="incomplete"):
        audit_outcome(queries, entries, [], [])
    ok = [audited(queries["p2"], "PRESENT"), audited(queries["a1"], "ABSENT")]
    removed, cells = audit_outcome(queries, entries, ok + [audited(queries["p1"], "UNKNOWN")], [])
    assert removed == {"p1", "a1"}  # the disputed query and its matched control
    assert cells["SCRUBD-CD|PRESENT"] == {"reviewed": 2, "errors": 1}
    two_errors = [audited(queries["p1"], "ABSENT"), audited(queries["p2"], "UNKNOWN")]
    with pytest.raises(ValueError, match="Systematic"):
        audit_outcome(queries, entries, two_errors + [ok[1]], [])
    removed, _ = audit_outcome(queries, entries, two_errors + [ok[1]], ["SCRUBD-CD|PRESENT"])
    assert removed == {"p1", "a1", "p2", "a2"}


def test_primary_selection_respects_order_corrections_groups_and_unknowns() -> None:
    heldout = [
        rq("p1", "PRESENT", "g1"),
        rq("p2", "PRESENT", "g1"),
        rq("p3", "PRESENT", "g3"),
        rq("a1", "ABSENT", "g4"),
        rq("x", "ABSENT", "g5"),
    ]
    queue = [
        {"query_id": q, "presentation_order": i, "polarity_queue": v, "group_id": g}
        for i, (q, v, g) in enumerate(
            [("p1", "PRESENT", "g1"), ("a1", "ABSENT", "g4"), ("p3", "PRESENT", "g3")], start=1
        )
    ]
    with pytest.raises(ValueError, match="incomplete"):
        primary_outcome(heldout, queue, [], 2)
    reviews = [
        review(query_id="p1", final_verdict="PRESENT"),
        review(query_id="a1", upstream_verdict="ABSENT", final_verdict="PRESENT"),
        review(query_id="p3", final_verdict="UNKNOWN", input_sufficient=False, vulnerable_lines=[]),
    ]
    primary, secondary, ties = primary_outcome(heldout, queue, reviews, 2)
    assert [(q.query_id, q.label, q.label_source) for q in primary] == [
        ("a1", "PRESENT", "locally_reviewed"),
        ("p1", "PRESENT", "locally_reviewed"),
    ]
    assert primary[1].vulnerable_lines == [4]
    # p2 shares p1's group; p3 was UNKNOWN and leaves every held-out view.
    assert [(q.query_id, q.label_source) for q in secondary] == [
        ("p2", "upstream_reviewed"),
        ("x", "upstream_reviewed"),
    ]
    assert ties == []


def test_smartbugs_external_uses_only_lines_of_the_exact_artifact(ledger: Ledger) -> None:
    from audit_distill.data.candidates import candidates
    from audit_distill.data.freeze import smartbugs_external
    from audit_distill.data.groups import build_groups
    from audit_distill.data.inventory import publish

    code = "contract C {\n  function f() public {\n    msg.sender.call.value(1)();\n  }\n}\n"
    art = ledger.artifact("smartbugs", "reentrancy/c.sol", code.encode())
    for native_id, lines in [("sb", [3]), ("plain", [])]:
        ledger.assess(
            art,
            annotation=ledger.config.datasets["smartbugs"].path / "labels.json",
            native_id=native_id,
            prop="reentrancy",
            verdict="PRESENT",
            kind="FILE",
            scope="FILE",
            checks=["REENTRANCY"],
            lines=lines,
        )
    other = ledger.artifact("smartbugs", "reentrancy/d.sol", code.replace("f()", "g()").encode())
    ledger.assess(
        other,
        annotation=ledger.config.datasets["smartbugs"].path / "labels.json",
        native_id="nolines",
        prop="reentrancy",
        verdict="PRESENT",
        kind="FILE",
        scope="FILE",
        checks=["REENTRANCY"],
    )
    qs, cs, ex = candidates(ledger, lambda _: 1)
    gs, edges = build_groups(list(ledger.artifacts.values()), qs, ledger.config)
    publish(ledger.config, ledger, qs, gs, edges, cs, ex, {})
    rows = smartbugs_external(ledger.config.output_dir)
    assert [(r["artifact_id"], r["vulnerable_lines"]) for r in rows] == [(art.artifact_id, [3])]
