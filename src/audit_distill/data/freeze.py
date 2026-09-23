"""Freeze the v2.2 release after the human reviews are complete.

Freeze applies recorded human decisions and never invents one. It fails with the
missing work listed when a queue is incomplete, a training-audit stratum shows a
systematic error, or a support/breadth gate no longer passes.
"""

import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

import pyarrow.parquet as pq

from audit_distill.data.inventory import read_records, write_records
from audit_distill.data.labeling import (
    QUEUE_FILES,
    LabelReview,
    load_reviews,
    next_item,
    read_jsonl,
)
from audit_distill.data.records import Assessment, CandidateQuery
from audit_distill.data.release import (
    POLARITIES,
    ReleaseConfig,
    ReleaseQuery,
    both_polarity_collections,
    portable_config,
    verify_release,
)
from audit_distill.data.scopes import digest
from audit_distill.provenance import file_sha256, project_provenance, write_json

Cohort = Literal["train", "validation", "test_primary", "test_secondary"]
# Two or more disagreements among the (up to five) audited cards of one stratum are
# treated as systematic and need an explicit stratum decision before freezing.
SYSTEMATIC_ERRORS = 2


class FrozenQuery(ReleaseQuery):
    cohort: Cohort
    label: Literal["PRESENT", "ABSENT"]
    label_source: Literal["upstream_reviewed", "locally_reviewed"]
    vulnerable_lines: list[int]


def audit_outcome(
    queries: dict[str, ReleaseQuery],
    audit: list[dict[str, object]],
    reviews: list[LabelReview],
    quarantined_cells: list[str],
) -> tuple[set[str], dict[str, dict[str, int]]]:
    """Return query IDs removed from train/validation and per-stratum audit results."""
    done = {r.query_id: r for r in reviews if r.queue == "training_audit"}
    missing = [e["query_id"] for e in audit if e["query_id"] not in done]
    if missing:
        raise ValueError(f"Training-label audit incomplete: {len(missing)} card(s) remain")
    cells: dict[str, dict[str, int]] = defaultdict(lambda: {"reviewed": 0, "errors": 0})
    removed: set[str] = set()
    for entry in audit:
        review = done[str(entry["query_id"])]
        cell = f"{entry['cell']['collection']}|{entry['cell']['upstream_verdict']}"
        cells[cell]["reviewed"] += 1
        if review.final_verdict != review.upstream_verdict:
            cells[cell]["errors"] += 1
            # A disputed training label is quarantined with its matched partner, not relabeled.
            removed.add(review.query_id)
    systematic = sorted(
        cell
        for cell, row in cells.items()
        if row["errors"] >= SYSTEMATIC_ERRORS and cell not in quarantined_cells
    )
    if systematic:
        raise ValueError(
            "Systematic audit errors need a stratum decision (quarantine the cell in "
            f"configs/release.yaml `quarantined_cells` or fix the mapping): {systematic}"
        )
    for query in queries.values():
        if f"{query.collection}|{query.upstream_verdict}" in quarantined_cells:
            removed.add(query.query_id)
    # Pairwise removal keeps every remaining partition exactly matched and balanced.
    removed |= {queries[q].match_partner for q in removed if queries[q].match_partner}
    return removed, dict(sorted(cells.items()))


def primary_outcome(
    heldout: list[ReleaseQuery],
    primary: list[dict[str, object]],
    reviews: list[LabelReview],
    quota: int,
) -> tuple[list[FrozenQuery], list[FrozenQuery], list[str]]:
    if next_item("primary_test", primary, reviews, quota) is not None:
        remaining = sum(
            e["query_id"] not in {r.query_id for r in reviews if r.queue == "primary_test"}
            for e in primary
        )
        raise ValueError(f"Primary test review incomplete: {remaining} queued card(s) remain")
    done = {r.query_id: r for r in reviews if r.queue == "primary_test"}
    by_id = {q.query_id: q for q in heldout}
    chosen: dict[str, list[str]] = {v: [] for v in POLARITIES}
    groups: dict[str, set[str]] = {v: set() for v in POLARITIES}
    tie_breaks: list[str] = []
    for entry in sorted(primary, key=lambda e: int(e["presentation_order"])):
        review = done.get(str(entry["query_id"]))
        if review is None or not review.accepted:
            continue
        verdict = review.final_verdict
        group = by_id[review.query_id].group_id
        if len(chosen[verdict]) >= quota:
            continue
        if group in groups[verdict]:
            tie_breaks.append(f"{review.query_id}: group already in {verdict} primary set")
            continue
        chosen[verdict].append(review.query_id)
        groups[verdict].add(group)
    primary_ids = {q for ids in chosen.values() for q in ids}
    test_primary: list[FrozenQuery] = []
    test_secondary: list[FrozenQuery] = []
    for query in sorted(heldout, key=lambda q: q.query_id):
        review = done.get(query.query_id)
        if review is not None and not review.accepted:
            continue  # Reviewed as UNKNOWN: excluded from every held-out view.
        label = review.final_verdict if review else query.upstream_verdict
        frozen = FrozenQuery(
            **query.model_dump(),
            cohort="test_primary" if query.query_id in primary_ids else "test_secondary",
            label=label,
            label_source="locally_reviewed" if review else "upstream_reviewed",
            vulnerable_lines=review.vulnerable_lines if review else [],
        )
        (test_primary if query.query_id in primary_ids else test_secondary).append(frozen)
    return test_primary, test_secondary, tie_breaks


def smartbugs_external(inventory: Path) -> list[dict[str, object]]:
    """Protected SmartBugs positives with reviewed lines on the exact supplied artifact.

    Membership needs native SmartBugs PRESENT support. Lines come only from reviewed
    PRESENT annotations of the representative artifact itself (SmartBugs or Salzano's
    manual re-annotation of the same curated file); coordinates are never transferred.
    """
    queries = read_records(inventory / "queries.parquet", CandidateQuery)
    evidence = {
        a.assessment_id: a for a in read_records(inventory / "assessments.parquet", Assessment)
    }
    sources = {
        r["artifact_id"]: r["source"]
        for r in pq.read_table(
            inventory / "artifacts.parquet", columns=["artifact_id", "source"]
        ).to_pylist()
    }
    rows = []
    for query in sorted(queries, key=lambda q: q.query_id):
        support = [evidence[aid] for aid in query.assessment_ids]
        if query.role != "smartbugs_external" or query.proposed_verdict != "PRESENT":
            continue
        if not any(
            sources[a.artifact_id] == "smartbugs" and a.native_verdict == "PRESENT" for a in support
        ):
            continue
        lines = sorted(
            {
                line
                for a in support
                if a.artifact_id == query.artifact_id
                and a.evidence_tier == "UPSTREAM_REVIEWED"
                and a.native_verdict == "PRESENT"
                for line in a.native_lines
            }
        )
        if lines:
            rows.append(
                {
                    "query_id": query.query_id,
                    "artifact_id": query.artifact_id,
                    "group_id": query.group_id,
                    "model_input_sha256": query.model_input_sha256,
                    "scope_kind": query.scope.kind,
                    "scope_name": query.scope.name,
                    "label": "PRESENT",
                    "label_source": "upstream_reviewed",
                    "vulnerable_lines": lines,
                }
            )
    return rows


def gate_report(
    cohorts: dict[str, list[FrozenQuery]], config: ReleaseConfig
) -> dict[str, dict[str, object]]:
    minimums = {
        "train": config.min_groups_per_polarity.train,
        "validation": config.min_groups_per_polarity.validation,
        "test_primary": config.min_groups_per_polarity.heldout,
    }
    report: dict[str, dict[str, object]] = {}
    for name, minimum in minimums.items():
        rows = cohorts[name]
        groups = {v: len({q.group_id for q in rows if q.label == v}) for v in POLARITIES}
        relabeled = [q.model_copy(update={"upstream_verdict": q.label}) for q in rows]
        breadth = both_polarity_collections(relabeled)
        report[name] = {
            "groups": groups,
            "minimum": minimum,
            "both_polarity_collections": breadth,
            "passed": all(n >= minimum for n in groups.values()) and bool(breadth),
        }
    return report


def freeze(config: ReleaseConfig, reviews_path: Path, root: Path) -> dict[str, object]:
    release = config.output_dir
    manifest = verify_release(release)
    if (release / "dataset_freeze.json").exists():
        raise ValueError("This release is already frozen; corrections need a new release")
    snapshot = json.loads((release / "effective_release_config.json").read_text(encoding="utf-8"))
    current = portable_config(config)
    if {k: v for k, v in current.items() if k != "quarantined_cells"} != {
        k: v for k, v in snapshot.items() if k != "quarantined_cells"
    }:
        raise ValueError("Release settings changed after the split; rebuild instead of freezing")
    queries = {
        row["query_id"]: ReleaseQuery.model_validate(row)
        for row in read_jsonl(release / "release_queries.jsonl")
    }
    audit = read_jsonl(release / QUEUE_FILES["training_audit"])
    primary = read_jsonl(release / QUEUE_FILES["primary_test"])
    reviews = load_reviews(reviews_path, release)
    removed, audit_cells = audit_outcome(queries, audit, reviews, config.quarantined_cells)
    audited = {r.query_id: r for r in reviews if r.queue == "training_audit"}
    cohorts: dict[str, list[FrozenQuery]] = {"train": [], "validation": []}
    for query in sorted(queries.values(), key=lambda q: q.query_id):
        if query.partition in cohorts and query.query_id not in removed:
            review = audited.get(query.query_id)
            cohorts[str(query.partition)].append(
                FrozenQuery(
                    **query.model_dump(),
                    cohort=query.partition,
                    label=query.upstream_verdict,
                    label_source="locally_reviewed" if review else "upstream_reviewed",
                    vulnerable_lines=review.vulnerable_lines if review else [],
                )
            )
    heldout = [q for q in queries.values() if q.partition == "heldout"]
    cohorts["test_primary"], cohorts["test_secondary"], tie_breaks = primary_outcome(
        heldout, primary, reviews, config.primary_per_polarity
    )
    gates = gate_report(cohorts, config)
    failed = [name for name, row in gates.items() if not row["passed"]]
    if failed:
        raise ValueError(f"Support/breadth gates failed after review: {failed} {gates}")
    external = smartbugs_external(config.inventory_dir)
    reviewers = sorted({r.reviewer for r in reviews})
    with tempfile.TemporaryDirectory(prefix=".v2.2-freeze-", dir=release.parent) as temporary:
        stage = Path(temporary)
        for name, rows in cohorts.items():
            write_records(stage / f"{name}.parquet", rows, FrozenQuery)
        with (stage / "external_smartbugs.jsonl").open("w", encoding="utf-8") as stream:
            for row in external:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
        (stage / "reviews.jsonl").write_bytes(reviews_path.read_bytes())
        files = {p.name: file_sha256(p) for p in sorted(stage.iterdir())}
        statistics = {
            name: {
                "queries": dict(sorted(Counter(q.label for q in rows).items())),
                "by_collection": dict(
                    sorted(Counter(f"{q.collection}|{q.label}" for q in rows).items())
                ),
                "locally_reviewed": sum(q.label_source == "locally_reviewed" for q in rows),
            }
            for name, rows in cohorts.items()
        }
        record = {
            "spec_version": "2.2",
            "state": "frozen",
            "release_content_sha256": manifest["release_content_sha256"],
            "inventory_content_sha256": manifest["inventory_content_sha256"],
            "files": files,
            "freeze_content_sha256": digest(files),
            "reviewers": reviewers,
            "reviewer_kind": "human",
            "training_audit": {
                "cells": audit_cells,
                "quarantined_cells": config.quarantined_cells,
                "removed_train_validation_queries": len(removed),
            },
            "primary_tie_breaks": tie_breaks,
            "gates": gates,
            "statistics": statistics,
            "external": {
                "smartbugs_positive_queries": len(external),
                "modern_forge": "unavailable: out of scope in SPEC v2.2",
            },
            "project": project_provenance(root),
            "teacher_generation_run": False,
            "training_run": False,
        }
        write_json(stage / "dataset_freeze.json", record)
        for path in sorted(stage.iterdir()):
            if path.name != "dataset_freeze.json":
                os.replace(path, release / path.name)
        os.replace(stage / "dataset_freeze.json", release / "dataset_freeze.json")
    return record
