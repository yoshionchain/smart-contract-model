"""Current reentrancy evidence-boundary and reproducibility regressions."""

import csv
import json
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from audit_distill.data.candidates import candidates, canonical_payload
from audit_distill.data.groups import Unit, build_groups, near_clone_pairs, skeleton
from audit_distill.data.identity import solidity_tokens
from audit_distill.data.ingest import parse_lines, salzano
from audit_distill.data.inventory import publish, read_records, verify_manifest, write_records
from audit_distill.data.ledger import Ledger
from audit_distill.data.native import cgt, native_verdict, scrubd
from audit_distill.data.records import Artifact, Assessment, CandidateQuery
from audit_distill.data.scopes import resolve_scope
from audit_distill.data.settings import DataConfig, load_data_config


def add(
    ledger: Ledger,
    code: str,
    *,
    source: str = "scrubd",
    path: str = "x.sol",
    verdict: str = "PRESENT",
    check: str = "REENTRANCY",
    kind: str = "FILE",
    scope: str = "FILE",
    prop: str = "RE",
    keys: list[str] | None = None,
) -> Artifact:
    artifact = ledger.artifact(source, path, code.encode(), project_keys=keys)
    ledger.assess(
        artifact,
        annotation=ledger.config.datasets[source].path / "labels.json",
        native_id=str(len(ledger.assessments)),
        prop=prop,
        verdict=verdict,
        kind=kind,
        scope=scope,
        checks=[check],
    )
    return artifact


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", "UNKNOWN"),
        ("n/a", "UNKNOWN"),
        ("0", "ABSENT"),
        ("f", "ABSENT"),
        ("1", "PRESENT"),
        ("t", "PRESENT"),
    ],
)
def test_native_verdict(value: str, expected: str) -> None:
    assert native_verdict(value) == expected
    with pytest.raises(ValueError):
        native_verdict("safe")


def test_config_rejects_legacy_or_external_reassignment() -> None:
    current = load_data_config(Path("configs/project.yaml")).model_dump()
    with pytest.raises(ValidationError):
        DataConfig.model_validate(current | {"spec_version": "1.3"})
    config = load_data_config(Path("configs/project.yaml")).model_dump()
    config["datasets"]["forge"]["role"] = "development"
    with pytest.raises(ValidationError, match="Protected"):
        DataConfig.model_validate(config)


def test_comments_coordinates_and_literals(ledger: Ledger) -> None:
    code = '// reentrancy\r\ncontract C { string s = "// literal {}"; /* hit */ }\r\n'
    a = ledger.artifact("scrubd", "x.sol", code.encode())
    assert len(a.code) == len(code)
    assert [(i, c) for i, c in enumerate(a.code) if c in "\r\n"] == [
        (i, c) for i, c in enumerate(code) if c in "\r\n"
    ]
    assert "reentrancy" not in a.code and '"// literal {}"' in a.code
    assert not a.ancestry_known
    assert a.raw_sha256 != a.code_sha256


def test_unreadable_and_unannotated_are_not_negatives(ledger: Ledger) -> None:
    ledger.artifact("dappscan", "no_label.sol", b"contract C {}")
    for i, raw in enumerate([b"", b"\xff", b"\x00", b"/* unterminated"]):
        artifact = ledger.artifact("scrubd", f"invalid{i}.sol", raw)
        assert artifact.code_identity_sha256 is None
    queries, conflicts, excluded = candidates(ledger, lambda _: 1)
    assert queries == conflicts == excluded == []


def test_scope_coordinates_overloads_and_literals() -> None:
    code = (
        "pragma solidity ^0.4.0;\r\ncontract C {\r\n"
        'function f(uint x) public { string memory s = "}"; }\r\n'
        "function f(address a) public {}\r\n}"
    )
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_scope(code, "FUNCTION", "f")
    scope = resolve_scope(code, "FUNCTION", "C.f(uint x)")
    assert scope.name == "C.f(uint x)" and scope.start_line == scope.end_line == 3
    assert resolve_scope(code, "CONTRACT", "C").start_line == 2
    with pytest.raises(ValueError):
        resolve_scope(code, "FUNCTION", "inheritedGuard")
    with pytest.raises(ValueError):
        resolve_scope("contract C {", "FILE", "FILE")


def test_duplicate_support_coalesces_without_losing_native_evidence(ledger: Ledger) -> None:
    add(ledger, "contract C { function f() public {} }", kind="FUNCTION", scope="f")
    add(
        ledger,
        "// note\ncontract C { function f() public {} }",
        source="cgt",
        kind="FUNCTION",
        scope="f",
    )
    queries, conflicts, _ = candidates(ledger, lambda _: 10)
    assert len(queries) == 1 and len(queries[0].assessment_ids) == 2
    assert not conflicts and not queries[0].training_ready
    assert queries[0].proposed_verdict == "PRESENT"


def test_negative_function_never_becomes_file_or_sibling_negative(ledger: Ledger) -> None:
    code = "contract C { function f() public {} function g() public {} }"
    add(ledger, code, verdict="ABSENT", kind="FUNCTION", scope="f")
    add(ledger, code, verdict="PRESENT", kind="FUNCTION", scope="g")
    queries, conflicts, _ = candidates(ledger, lambda _: 10)
    assert len(queries) == 2 and not conflicts
    assert {q.scope.name for q in queries} == {"C.f()", "C.g()"}
    assert {q.proposed_verdict for q in queries} == {"ABSENT", "PRESENT"}


def test_file_negative_conflict_quarantines_all_identity_checks(ledger: Ledger) -> None:
    code = "contract C { function f() public {} }"
    add(ledger, code, verdict="ABSENT")
    add(ledger, code, kind="FUNCTION", scope="f")
    add(ledger, code, kind="FUNCTION", scope="f", path="alias.sol")
    queries, conflicts, _ = candidates(ledger, lambda _: 10)
    assert len(conflicts) == 1 and conflicts[0].kind == "same_property_conflict"
    assert all(q.proposed_verdict == "UNKNOWN" for q in queries)
    assert all("unresolved_identity_disagreement" in q.review_required for q in queries)


def test_cross_property_disagreement_is_not_majority_voted(ledger: Ledger) -> None:
    code = "contract C {}"
    add(ledger, code, verdict="ABSENT", prop="Zeus RE")
    add(ledger, code, verdict="PRESENT", prop="eThor RE", source="cgt")
    queries, conflicts, _ = candidates(ledger, lambda _: 10)
    assert conflicts[0].kind == "cross_property_disagreement"
    assert queries[0].proposed_verdict == "UNKNOWN"


def test_unknown_overlength_and_unresolved_are_excluded_without_truncation(ledger: Ledger) -> None:
    art = add(ledger, "contract C {}", verdict="UNKNOWN")
    add(ledger, "contract D {}", path="long.sol")
    add(ledger, "contract E {}", path="bad_scope.sol", kind="FUNCTION", scope="missing")
    queries, _, excluded = candidates(ledger, lambda _: 6001)
    assert not queries
    assert {r["reason"] for r in excluded} == {
        "unknown_native_label",
        "overlength_source",
        "unresolved_scope",
    }
    assert art.code == "contract C {}"


def test_model_payload_has_no_native_labels_paths_or_rationale(ledger: Ledger) -> None:
    art = add(ledger, "// PRESENT SWC107\ncontract C {}", path="PRESENT-secret.sol")
    query = candidates(ledger, lambda _: 2)[0][0]
    payload = canonical_payload(art, query.check_id, "Check definition", query.scope)
    serialized = json.dumps(payload)
    assert set(payload) == {"check_id", "definition", "scope", "assumptions", "source"}
    assert not any(value in serialized for value in ["PRESENT", "secret", "scrubd", "SWC107"])


def test_skeleton_renames_consistently_preserves_types_and_operators() -> None:
    left = skeleton(
        solidity_tokens(
            "pragma solidity 0.4.0; contract A { uint x = 4; function f() public { x += x; } }"
        )
    )
    right = skeleton(
        solidity_tokens(
            "pragma solidity 0.8.0; contract B { uint y = 99; function z() public { y += y; } }"
        )
    )
    assert left == right
    assert left != skeleton(
        solidity_tokens("contract B { uint y = 99; function z() public { y -= y; } }")
    )
    assert skeleton(['"hello"', "123", "uint256", "bytes32", "true"]) == [
        "LITERAL_STRING",
        "LITERAL_NUMBER",
        "uint256",
        "bytes32",
        "true",
    ]


def test_exact_near_clone_index_matches_brute_force() -> None:
    rng = random.Random(42)
    units = [
        Unit(
            str(i),
            "FILE",
            120 + rng.randrange(15),
            frozenset(str(g) for g in rng.sample(range(35), rng.randrange(20, 35))),
        )
        for i in range(80)
    ]
    expected = {
        (i, j)
        for i, a in enumerate(units)
        for j, b in enumerate(units)
        if i < j
        and min(a.token_count, b.token_count) / max(a.token_count, b.token_count) >= 0.8
        and len(a.grams & b.grams) / len(a.grams | b.grams) >= 0.85
    }
    assert {(i, j) for i, j, _ in near_clone_pairs(units, 0.85, 0.8)} == expected


def test_external_reservation_transitive_even_without_external_target_label(ledger: Ledger) -> None:
    add(ledger, "contract A { uint x; }", keys=["repo:one"])
    add(ledger, "contract B { address a; }", path="b.sol", keys=["repo:one", "repo:two"])
    ledger.artifact(
        "smartbugs", "not_target.sol", b"contract C { bool x; }", project_keys=["repo:two"]
    )
    queries = candidates(ledger, lambda _: 1)[0]
    groups, edges = build_groups(list(ledger.artifacts.values()), queries, ledger.config)
    assert len(groups) == 1 and all(q.role == "smartbugs_external" for q in queries)
    assert len({q.group_id for q in queries}) == 1
    assert all(e["active"] for e in edges)


def test_inactive_shared_dependencies_do_not_merge_unrelated_contexts(ledger: Ledger) -> None:
    add(ledger, "contract A { uint x; }", keys=["repo:one"])
    add(ledger, "contract B { address a; }", path="b.sol", keys=["repo:two"])
    ledger.artifact(
        "dappscan",
        "unused1.sol",
        b"library L { function f() public {} }",
        project_keys=["repo:one"],
    )
    ledger.artifact(
        "dappscan",
        "unused2.sol",
        b"library L { function f() public {} }",
        project_keys=["repo:two"],
    )
    queries = candidates(ledger, lambda _: 1)[0]
    groups, _ = build_groups(list(ledger.artifacts.values()), queries, ledger.config)
    assert len(groups) == 2


def test_salzano_corrected_labels_keep_non_target_evidence_without_queries(ledger: Ledger) -> None:
    root = ledger.config.datasets["salzano"].path
    (root / "csvs").mkdir()
    with (root / "csvs/sample_of_interest_with_code.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["label", "tag", "contract", "contract_code"])
        writer.writerow(["zeus_vulnerable", "no", "x", "contract C {}"])
        writer.writerow(
            ["zeus_safe", "1:access_control;99:access_control", "y", "contract D { uint n; }"]
        )
    salzano(ledger)
    queries, _, _ = candidates(ledger, lambda _: 3)
    negatives = [a for a in ledger.assessments if a.native_verdict == "ABSENT"]
    assert len(negatives) == 1 and "negative_coverage_review_required" in negatives[0].issues
    assert len(queries) == 1 and queries[0].proposed_verdict == "ABSENT"
    other = [a for a in ledger.assessments if a.native_property == "access_control"]
    assert len(other) == 1 and not other[0].candidate_checks
    assert "annotation_line_out_of_bounds" in other[0].issues


def test_scrubd_blank_and_function_provenance(ledger: Ledger) -> None:
    base = ledger.config.datasets["scrubd"].path / "SCRUBD-CD/data"
    (base / "solidity_codes").mkdir(parents=True)
    (base / "solidity_codes/0xabc.sol").write_text("contract C { function f() public {} }")
    (base / "labels.csv").write_text(
        "Smart Contract,Function Name,RE,UX,is_student,Comments\n0xabc,f,0,,1,original review\n"
    )
    scrubd(ledger)
    assert [a.native_verdict for a in ledger.assessments] == ["ABSENT", "UNKNOWN"]
    assert ledger.assessments[0].metadata["is_student"] == "1"
    queries, _, exclusions = candidates(ledger, lambda _: 1)
    assert len(queries) == 1 and queries[0].scope.kind == "FUNCTION"
    assert not exclusions  # The blank UX judgment is retained outside the active task.


def test_cgt_disallowed_original_is_inventory_only(ledger: Ledger) -> None:
    root = ledger.config.datasets["cgt"].path
    (root / "source").mkdir()
    (root / "source/fp.sol").write_text("contract C {}")
    (root / "consolidated.csv").write_text(
        "dataset;id;fp_sol;property;property_holds;swc;contractname;chain;addr\nSolidiFI;1;fp;reentrancy;t;107;C;;\n"
    )
    cgt(ledger)
    assert len(ledger.assessments) == 1
    queries, _, excluded = candidates(ledger, lambda _: 1)
    assert not queries and excluded[0]["reason"] == "excluded_original_collection"


def test_parquet_roundtrip_empty_and_populated(ledger: Ledger, tmp_path: Path) -> None:
    add(ledger, "contract C {}")
    qs = candidates(ledger, lambda _: 1)[0]
    for model, rows in [
        (Artifact, list(ledger.artifacts.values())),
        (Assessment, ledger.assessments),
        (CandidateQuery, qs),
    ]:
        path = tmp_path / (model.__name__ + ".parquet")
        write_records(path, rows, model)
        assert read_records(path, model) == rows
        write_records(path, [], model)
        assert read_records(path, model) == []


def test_publish_deterministic_inventory_not_freeze_and_preserves_reviews(ledger: Ledger) -> None:
    add(ledger, "contract C {}")
    qs, conflicts, excluded = candidates(ledger, lambda _: 1)
    gs, edges = build_groups(list(ledger.artifacts.values()), qs, ledger.config)
    first = publish(ledger.config, ledger, qs, gs, edges, conflicts, excluded, {})
    out = ledger.config.output_dir
    (out / "reviews.jsonl").write_text("human work must survive\n")
    second = publish(ledger.config, ledger, qs, gs, edges, conflicts, excluded, {})
    assert first == second and first["state"] == "inventory" and not first["training_ready"]
    assert (out / "reviews.jsonl").read_text() == "human work must survive\n"
    assert not (out / "train.parquet").exists()
    assert not (out / "dataset_freeze.json").exists()
    (out / "dataset_freeze.json").write_text("{}")
    with pytest.raises(ValueError, match="frozen"):
        publish(ledger.config, ledger, qs, gs, edges, conflicts, excluded, {})


@pytest.mark.parametrize(
    ("raw", "expected", "issue"),
    [("L2-L4, L8", [2, 3, 4, 8], False), ("N/A", [], False), ("unknown", [], True)],
)
def test_native_location_parsing(raw: str, expected: list[int], issue: bool) -> None:
    lines, flags = parse_lines(raw)
    assert lines == expected and bool(flags) == issue


def test_callback_type_is_not_a_second_function_declaration() -> None:
    from audit_distill.data.scopes import declarations

    code = "contract C { function f(function() external cb) public { cb(); } }"
    _, _, units = declarations(code)
    assert [u.name for u in units if u.kind == "FUNCTION"] == ["f"]
    with pytest.raises(ValueError):
        resolve_scope(code, "FUNCTION", "fallback")


def test_missing_scrubd_trailing_comments_are_empty(ledger: Ledger) -> None:
    base = ledger.config.datasets["scrubd"].path / "SCRUBD-CD/data"
    (base / "solidity_codes").mkdir(parents=True)
    (base / "solidity_codes/0xabc.sol").write_text("contract C { function f() public {} }")
    (base / "labels.csv").write_text(
        "Smart Contract,Function Name,RE,UX,is_student,Comments\n0xabc,f,0,1,1\n"
    )
    scrubd(ledger)
    assert all(a.rationale == "" for a in ledger.assessments)
    assert [a.native_verdict for a in ledger.assessments] == ["ABSENT", "PRESENT"]


def test_review_blind_input_and_manifest_tampering(ledger: Ledger) -> None:
    from audit_distill.data.labeling import query_card

    add(ledger, "contract C {}")
    qs, cs, ex = candidates(ledger, lambda _: 1)
    gs, edges = build_groups(list(ledger.artifacts.values()), qs, ledger.config)
    publish(ledger.config, ledger, qs, gs, edges, cs, ex, {})
    out = ledger.config.output_dir
    verify_manifest(out)
    blind = query_card(out, qs[0].query_id)
    assert "native_evidence" not in blind and "PRESENT" not in json.dumps(blind)
    revealed = query_card(out, qs[0].query_id, reveal=True)
    assert revealed["model_input"] == blind["model_input"]
    assert revealed["native_evidence"][0]["native_verdict"] == "PRESENT"
    (out / "conflicts.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="modified"):
        verify_manifest(out)


def test_publication_rejects_stale_input_hash(ledger: Ledger) -> None:
    add(ledger, "contract C {}")
    qs, cs, ex = candidates(ledger, lambda _: 1)
    gs, edges = build_groups(list(ledger.artifacts.values()), qs, ledger.config)
    qs[0].model_input_sha256 = "0" * 64
    with pytest.raises(ValueError, match="Stale"):
        publish(ledger.config, ledger, qs, gs, edges, cs, ex, {})


def test_assessed_function_clones_record_inactive_inventory_matches(ledger: Ledger) -> None:
    body = "function f(uint x) public returns(uint) { " + "x += 1; " * 15 + "return x; }"
    add(ledger, "contract A { " + body + " }", kind="FUNCTION", scope="f")
    inactive = ledger.artifact(
        "dappscan", "unused.sol", ("contract B { bool z; " + body + " }").encode()
    )
    qs = candidates(ledger, lambda _: 1)[0]
    groups, edges = build_groups(list(ledger.artifacts.values()), qs, ledger.config)
    assert len(groups) == 1
    assert inactive.code_identity_sha256 not in groups[0]["code_identities"]
    assert any(e["reason"] == "assessed_function_clone" and not e["active"] for e in edges)


def test_scbench_suicide_negative_remains_a_subtype(ledger: Ledger) -> None:
    from audit_distill.data.native import scbench

    base = ledger.config.datasets["scbench"].path / "Empirical Evaluation of Security Analyzers"
    (base / "Solidity").mkdir(parents=True)
    (base / "Tools_Labels").mkdir()
    (base / "Solidity/Suicide*0*x.sol").write_text("contract C {}")
    for prop in ["Reentrancy", "Suicide", "IntergerOU"]:
        (base / f"Tools_Labels/{prop}_labels.csv").write_text(
            "contract_address,label\n" + ("Suicide*0*x.sol,0\n" if prop == "Suicide" else "")
        )
    scbench(ledger)
    qs = candidates(ledger, lambda _: 1)[0]
    assert not qs
    assert ledger.assessments[0].native_property == "Suicide"
    assert ledger.assessments[0].native_verdict == "ABSENT"
    assert not ledger.assessments[0].candidate_checks


def test_forge_keywords_are_unverified_external_candidates(ledger: Ledger) -> None:
    from audit_distill.data.forge import forge

    base = ledger.config.datasets["forge"].path
    (base / "flatten/vfp").mkdir(parents=True)
    row = {
        "project_name": "report.pdf",
        "affected_files": {"C.sol": "contract C {}"},
        "findings": [
            {
                "id": 1,
                "title": "Possible reentrancy",
                "description": "Inspect original audit",
                "category": {"id": "CWE-862"},
                "files": ["C.sol"],
            }
        ],
    }
    (base / "flatten/vfp/one.json").write_text(json.dumps(row))
    forge(ledger)
    assert ledger.assessments[0].evidence_tier == "UNVERIFIED"
    qs = candidates(ledger, lambda _: 1)[0]
    assert all(q.role == "forge_external" and not q.training_ready for q in qs)
    assert all("unverified_native_evidence" in q.review_required for q in qs)


def test_source_pins_are_present_in_authoritative_spec() -> None:
    spec = Path("SPEC.md").read_text()
    config = load_data_config(Path("configs/project.yaml"))
    assert all(s.revision in spec for s in config.datasets.values())
    assert config.tokenizer.revision in spec


def test_v2_dappscan_retains_multiple_findings_and_unknown_files(
    ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    from audit_distill.data import ingest

    root = ledger.config.datasets["dappscan"].path
    base = root / "DAppSCAN-source/contracts/project"
    annotations = root / "DAppSCAN-source/SWCsource/project"
    base.mkdir(parents=True)
    annotations.mkdir(parents=True)
    (base / "positive.sol").write_text("contract C { function f() public {} }")
    (base / "unannotated.sol").write_text("contract D {}")
    row = {
        "filePath": "DAppSCAN-source/contracts/project/positive.sol",
        "SWCs": [
            {"category": "SWC-107-Reentrancy", "function": "f", "lineNumber": "L1"},
            {
                "category": "SWC-105-Unprotected Ether Withdrawal",
                "function": "f",
                "lineNumber": "L1",
            },
        ],
    }
    (annotations / "x.json").write_text(json.dumps(row))
    monkeypatch.setattr(
        ingest,
        "load_project_groups",
        lambda *_: (
            {"project": "p"},
            {"directory_metadata": {"project": {"repository_keys": ["github.com/owner/project"]}}},
        ),
    )
    ingest.dappscan(ledger)
    assert len(ledger.artifacts) == 2 and len(ledger.assessments) == 2
    qs = candidates(ledger, lambda _: 1)[0]
    assert {q.check_id for q in qs} == {"REENTRANCY"}
    assert not ledger.assessments[1].candidate_checks
    assert all(q.proposed_verdict == "PRESENT" for q in qs)


def test_smartbugs_non_target_sources_are_protected(ledger: Ledger) -> None:
    from audit_distill.data.ingest import smartbugs

    root = ledger.config.datasets["smartbugs"].path
    (root / "dataset").mkdir()
    (root / "dataset/x.sol").write_text("// SWC-101\ncontract C {}")
    (root / "vulnerabilities.json").write_text(
        json.dumps(
            [
                {
                    "name": "x.sol",
                    "path": "dataset/x.sol",
                    "pragma": "0.4.0",
                    "source": "https://example.test/source",
                    "vulnerabilities": [{"category": "arithmetic", "lines": [2]}],
                }
            ]
        )
    )
    smartbugs(ledger)
    assert len(ledger.artifacts) == len(ledger.assessments) == 1
    assert not candidates(ledger, lambda _: 1)[0]
    groups, _ = build_groups(list(ledger.artifacts.values()), [], ledger.config)
    assert groups[0]["role"] == "smartbugs_external"


def test_lexer_and_skeleton_preserve_operator_and_legacy_keyword_distinctions() -> None:
    assert solidity_tokens("a >>>= 1;") != solidity_tokens("a >> >= 1;")
    words = ["byte", "throw", "finney", "szabo", "layout", "at"]
    assert skeleton(words) == words
    assert skeleton(["require", "msg", "sender", "msg"]) == [
        "IDENT_0",
        "IDENT_1",
        "IDENT_2",
        "IDENT_1",
    ]


def test_reentrancy_version_and_registry_are_locked(ledger: Ledger) -> None:
    from audit_distill.data.settings import validate_taxonomy

    config = ledger.config.model_dump()
    for change in [
        {"spec_version": "2.0"},
        {"schema_version": "2"},
        {"active_checks": []},
        {"active_checks": ["REENTRANCY", "AUTHORIZATION"]},
    ]:
        with pytest.raises(ValidationError):
            DataConfig.model_validate(config | change)
    for change in [
        {"schema_version": "2"},
        {"swc_candidates": {"104": ["REENTRANCY"]}},
        {"negative_rules": {"missing": "ABSENT"}},
        {"checks": ledger.taxonomy["checks"] | {"AUTHORIZATION": {}}},
    ]:
        with pytest.raises(ValueError):
            validate_taxonomy(ledger.taxonomy | change)
    add(ledger, "contract C {}")
    query = candidates(ledger, lambda _: 1)[0][0]
    for change in [{"check_id": "AUTHORIZATION"}, {"schema_version": "2"}]:
        with pytest.raises(ValidationError):
            CandidateQuery.model_validate(query.model_dump() | change)


def test_inactive_property_disagreement_does_not_relabel_reentrancy(ledger: Ledger) -> None:
    art = add(ledger, "contract C {}")
    for verdict in ["PRESENT", "ABSENT"]:
        ledger.assess(
            art,
            annotation=ledger.config.datasets["scrubd"].path / "labels.json",
            native_id=f"other:{verdict}",
            prop="other_property",
            verdict=verdict,
            checks=[],
        )
    queries, conflicts, _ = candidates(ledger, lambda _: 1)
    assert len(ledger.assessments) == 3
    assert len(queries) == 1 and queries[0].proposed_verdict == "PRESENT"
    assert not conflicts and not queries[0].training_ready


def test_persisted_baseline_validation_and_evidence_counts(ledger: Ledger) -> None:
    from audit_distill.data.validate import validate_baseline

    code = "pragma solidity ^0.8.0; contract C {}"
    add(ledger, code)
    add(ledger, code, source="cgt")
    ledger.assessments[-1].evidence_tier = "UNVERIFIED"
    qs, cs, ex = candidates(ledger, lambda _: 1)
    gs, edges = build_groups(list(ledger.artifacts.values()), qs, ledger.config)
    publish(ledger.config, ledger, qs, gs, edges, cs, ex, {})
    out = ledger.config.output_dir
    result = validate_baseline(out)
    assert result["mechanical_validation"] == "PASS" and not result["training_ready"]
    stats = json.loads((out / "dataset_statistics.json").read_text())["baseline"]
    assert stats["development_source_identities"] == 1
    cells = [c for c in stats["support_cells"] if c["dimension"] == "evidence"]
    assert len(cells) == 1 and cells[0]["value"] == "has_upstream_reviewed_support"
    assert cells[0]["queries"] == cells[0]["groups"] == 1
    assert stats["compiler_era_cells"][0]["first_pragma_minor"] == "0.8"
    assert (
        sum(c["queries"] for c in stats["support_cells"] if c["dimension"] == "supporting_source")
        == 2
    )  # Overlapping support is explicit.


def test_baseline_cannot_overwrite_or_read_old_manifest(ledger: Ledger) -> None:

    add(ledger, "contract C {}")
    qs, cs, ex = candidates(ledger, lambda _: 1)
    gs, edges = build_groups(list(ledger.artifacts.values()), qs, ledger.config)
    out = ledger.config.output_dir
    out.mkdir()
    path = out / "dataset_manifest.json"
    old = '{"spec_version": "2.0", "schema_version": "2", "state": "inventory"}'
    path.write_text(old)
    with pytest.raises(ValueError, match="incompatible"):
        publish(ledger.config, ledger, qs, gs, edges, cs, ex, {})
    with pytest.raises(ValueError, match="v2.1"):
        verify_manifest(out)
    assert path.read_text() == old


def test_current_record_schemas_match_exports(tmp_path: Path) -> None:
    from audit_distill.data.schema import write_schemas

    write_schemas(tmp_path)
    exported = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.json"))
    assert exported == sorted(p.relative_to("schemas") for p in Path("schemas").rglob("*.json"))
    for path in exported:
        assert (tmp_path / path).read_bytes() == (Path("schemas") / path).read_bytes()


def test_baseline_content_is_independent_of_record_order(ledger: Ledger) -> None:
    add(ledger, "contract C { uint x; }", verdict="ABSENT")
    add(ledger, "contract D { address a; }", path="d.sol")
    add(ledger, "contract E {}", path="e.sol", kind="FUNCTION", scope="missing")
    add(ledger, "contract F {}", path="f.sol", verdict="UNKNOWN")
    qs, cs, ex = candidates(ledger, lambda _: 1)
    gs, edges = build_groups(list(ledger.artifacts.values()), qs, ledger.config)
    first = publish(ledger.config, ledger, qs, gs, edges, cs, ex, {})
    ledger.assessments.reverse()
    ledger.artifacts = dict(reversed(list(ledger.artifacts.items())))
    qs, cs, ex = candidates(ledger, lambda _: 1)
    gs, edges = build_groups(list(ledger.artifacts.values()), qs, ledger.config)
    second = publish(
        ledger.config, ledger, list(reversed(qs)), gs, list(reversed(edges)), cs, ex, {}
    )
    assert first["dataset_content_sha256"] == second["dataset_content_sha256"]


def test_exact_source_budget_uses_numbered_input_without_truncation(ledger: Ledger) -> None:
    first = add(ledger, "contract C0 {}")
    second = add(ledger, "contract C1 {}", path="long.sol")
    inputs: list[str] = []

    def count_tokens(code: str) -> int:
        inputs.append(code)
        return 6000 if "C0" in code else 6001

    qs, _, exclusions = candidates(ledger, count_tokens)
    assert len(qs) == 1 and qs[0].artifact_id == first.artifact_id
    assert first.code_tokens == 6000 and second.code == "contract C1 {}"
    assert inputs == ["0001 | contract C0 {}", "0001 | contract C1 {}"]
    assert exclusions[0]["reason"] == "overlength_source"


def test_smartbugs_native_lines_and_leakage_stripping(ledger: Ledger) -> None:
    from audit_distill.data.ingest import smartbugs

    root = ledger.config.datasets["smartbugs"].path
    (root / "dataset").mkdir()
    code = "/* @vulnerable_at_lines: 3 */\r\n// REENTRANCY\r\ncontract C {}\r\n"
    (root / "dataset/x.sol").write_bytes(code.encode())
    (root / "dataset/unannotated.sol").write_text("contract D {}")
    entry = {
        "name": "x.sol",
        "path": "dataset/x.sol",
        "vulnerabilities": [{"category": "reentrancy", "lines": [3, 99]}],
    }
    (root / "vulnerabilities.json").write_text(json.dumps([entry]))
    smartbugs(ledger)
    qs, _, _ = candidates(ledger, lambda _: 1)
    assert len(qs) == 1
    artifact = ledger.artifacts[qs[0].artifact_id]
    assert artifact.code.count("\r\n") == 3
    assert "vulnerable_at" not in artifact.code and "REENTRANCY" not in artifact.code
    assert artifact.code.splitlines()[2] == "contract C {}"
    assert ledger.assessments[0].native_lines == [3, 99]
    assert "native_location_source_alignment" in qs[0].review_required
    assert all(a.role == "smartbugs_external" for a in ledger.artifacts.values())


def test_missing_dappscan_annotation_target_aborts(
    ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    from audit_distill.data import ingest

    root = ledger.config.datasets["dappscan"].path
    source = root / "DAppSCAN-source/contracts/project"
    annotations = root / "DAppSCAN-source/SWCsource/project"
    source.mkdir(parents=True)
    annotations.mkdir(parents=True)
    (source / "x.sol").write_text("contract C {}")
    (annotations / "x.json").write_text(
        json.dumps({"filePath": "DAppSCAN-source/contracts/project/missing.sol", "SWCs": []})
    )
    monkeypatch.setattr(
        ingest,
        "load_project_groups",
        lambda *_: ({"project": "p"}, {"directory_metadata": {"project": {"repository_keys": []}}}),
    )
    with pytest.raises(ValueError, match="Missing DAppSCAN annotation target"):
        ingest.dappscan(ledger)


@pytest.mark.parametrize("relative", ["../outside.sol", "/outside.sol", "a\\outside.sol"])
def test_upstream_paths_cannot_escape_checkout(tmp_path: Path, relative: str) -> None:
    from audit_distill.data.io import contained_path

    with pytest.raises(ValueError, match="Unsafe"):
        contained_path(tmp_path, relative)
