"""Build the final dataset from the inventory: eligibility, balancing and grouped split.

Labels are the upstream human annotations under the SWC-107 reentrancy convention;
this stage never edits them. It writes train/validation/test cohorts that carry the
exact model input, plus the protected SmartBugs external positives.
"""

import json
import logging
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

import pyarrow.parquet as pq
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.model_selection import StratifiedGroupKFold

from audit_distill.config import ConfigModel
from audit_distill.data.candidates import canonical_payload
from audit_distill.data.inventory import read_records, verify_manifest, write_jsonl, write_records
from audit_distill.data.records import Assessment, CandidateQuery
from audit_distill.data.scopes import digest
from audit_distill.provenance import file_sha256, project_provenance, write_json

logger = logging.getLogger(__name__)

Polarity = Literal["PRESENT", "ABSENT"]
Partition = Literal["train", "validation", "test"]
MatchKey = Literal["collection", "scope_kind", "pragma_minor"]
PARTITIONS: tuple[Partition, ...] = ("train", "validation", "test")
POLARITIES: tuple[Polarity, ...] = ("PRESENT", "ABSENT")


class Gates(ConfigModel):
    train: Literal[30]
    validation: Literal[5]
    test: Literal[10]


class ReleaseConfig(ConfigModel):
    spec_version: Literal["2.3"]
    inventory_dir: Path
    inventory_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_dir: Path
    seed: Literal[42]
    coverage_confirmed_sources: dict[str, str]
    max_queries_per_group_polarity: Literal[3]
    match_levels: list[list[MatchKey]]
    folds: Literal[7]
    test_fold: Literal[0]
    validation_fold: Literal[1]
    split_seed_first: Literal[42]
    split_seed_last: Literal[1041]
    min_groups_per_polarity: Gates

    @model_validator(mode="after")
    def complete_matching(self) -> "ReleaseConfig":
        if not self.match_levels or self.match_levels[-1] != []:
            raise ValueError("Matching must end with the explicit catch-all level []")
        return self


def load_release_config(path: Path, *, root: Path | None = None) -> ReleaseConfig:
    root = (root or path.resolve().parent.parent).resolve()
    config = ReleaseConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    return config.model_copy(
        update={
            "inventory_dir": (root / config.inventory_dir).resolve(),
            "output_dir": (root / config.output_dir).resolve(),
        }
    )


class ReleaseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["2.3"] = "2.3"


class ReleaseQuery(ReleaseRecord):
    """One eligible query; `label` is the upstream human annotation, never edited."""

    query_id: str
    artifact_id: str
    group_id: str
    code_identity_sha256: str
    model_input_sha256: str
    label: Polarity
    collection: str
    scope_kind: Literal["FILE", "CONTRACT", "FUNCTION"]
    scope_name: str
    scope_start_line: int
    scope_end_line: int
    pragma_minor: str
    assessment_ids: list[str]
    qualifying_assessment_ids: list[str] = Field(min_length=1)
    # Upstream vulnerable lines annotated on this exact artifact (PRESENT only).
    vulnerable_lines: list[int] = Field(default_factory=list)
    match_role: Literal["case", "control"] | None = None
    match_partner: str | None = None
    match_level: int | None = None
    partition: Partition | None = None

    def key(self, fields: list[MatchKey]) -> tuple[str, ...]:
        return tuple(getattr(self, name) for name in fields)


class CohortQuery(ReleaseQuery):
    """A final cohort row: the query plus its exact model input payload."""

    check_id: Literal["REENTRANCY"]
    definition: str
    assumptions: list[str]
    source: str


class ExternalQuery(ReleaseRecord):
    """A protected SmartBugs positive with independent lines; never trained on."""

    query_id: str
    artifact_id: str
    group_id: str
    model_input_sha256: str
    label: Literal["PRESENT"]
    scope_kind: Literal["FILE", "CONTRACT", "FUNCTION"]
    scope_name: str
    vulnerable_lines: list[int] = Field(min_length=1)
    check_id: Literal["REENTRANCY"]
    definition: str
    assumptions: list[str]
    source: str


def pragma_minor(code: str) -> str:
    """First-pragma compiler screen; not a deployment date or EVM fork."""
    match = re.search(r"\bpragma\s+solidity\b[^;]*?(0\.\d+)", code)
    return match[1] if match else "unspecified"


def exact_lines(query: CandidateQuery, assessments: dict[str, Assessment]) -> list[int]:
    """Reviewed PRESENT lines on the representative artifact; never transferred."""
    return sorted(
        {
            line
            for aid in query.assessment_ids
            if assessments[aid].artifact_id == query.artifact_id
            and assessments[aid].evidence_tier == "UPSTREAM_REVIEWED"
            and assessments[aid].native_verdict == "PRESENT"
            for line in assessments[aid].native_lines
        }
    )


def eligibility(
    queries: list[CandidateQuery],
    assessments: dict[str, Assessment],
    sources: dict[str, str],
    codes: dict[str, str],
    config: ReleaseConfig,
) -> tuple[list[ReleaseQuery], list[dict[str, str]]]:
    """Admit development queries with upstream-reviewed, coverage-supported evidence."""
    eligible: list[ReleaseQuery] = []
    exclusions: list[dict[str, str]] = []
    for query in sorted(queries, key=lambda q: q.query_id):
        if query.role != "development":
            continue  # External reservations are never development data.
        if query.proposed_verdict not in POLARITIES:
            exclusions.append({"query_id": query.query_id, "reason": "unknown_or_disputed"})
            continue
        reviewed = [
            assessments[a]
            for a in query.assessment_ids
            if assessments[a].evidence_tier == "UPSTREAM_REVIEWED"
        ]
        if not reviewed:
            exclusions.append({"query_id": query.query_id, "reason": "unverified_evidence_only"})
            continue
        qualifying = [
            a
            for a in reviewed
            if a.native_verdict == query.proposed_verdict
            and (
                "negative_coverage_review_required" not in a.issues
                or sources[a.artifact_id] in config.coverage_confirmed_sources
            )
        ]
        if not qualifying:
            exclusions.append(
                {"query_id": query.query_id, "reason": "negative_coverage_unconfirmed"}
            )
            continue
        if query.group_id is None:
            raise ValueError(f"Development query without a group: {query.query_id}")
        eligible.append(
            ReleaseQuery(
                query_id=query.query_id,
                artifact_id=query.artifact_id,
                group_id=query.group_id,
                code_identity_sha256=query.code_identity_sha256,
                model_input_sha256=query.model_input_sha256,
                label=query.proposed_verdict,
                collection="+".join(sorted(query.original_collections)),
                scope_kind=query.scope.kind,
                scope_name=query.scope.name,
                scope_start_line=query.scope.start_line,
                scope_end_line=query.scope.end_line,
                pragma_minor=pragma_minor(codes[query.artifact_id]),
                assessment_ids=sorted(query.assessment_ids),
                qualifying_assessment_ids=sorted(a.assessment_id for a in qualifying),
                vulnerable_lines=exact_lines(query, assessments)
                if query.proposed_verdict == "PRESENT"
                else [],
            )
        )
    return eligible, exclusions


def cap_group_queries(
    eligible: list[ReleaseQuery], cap: int, seed: int
) -> tuple[list[ReleaseQuery], list[dict[str, str]]]:
    """Keep at most `cap` queries per group and polarity, in seeded hash order.

    Many functions of one project are not independent evidence; the cap stops a few
    large projects from dominating a partition or its matched controls.
    """
    kept: list[ReleaseQuery] = []
    dropped: list[dict[str, str]] = []
    counts: Counter[tuple[str, str]] = Counter()
    for query in sorted(eligible, key=lambda q: digest([seed, q.query_id])):
        key = (query.group_id, query.label)
        if counts[key] < cap:
            counts[key] += 1
            kept.append(query)
        else:
            dropped.append({"query_id": query.query_id, "reason": "group_query_cap"})
    return sorted(kept, key=lambda q: q.query_id), dropped


def matched_selection(
    eligible: list[ReleaseQuery], levels: list[list[MatchKey]], seed: int
) -> tuple[list[ReleaseQuery], list[dict[str, str]]]:
    """Pair every minority-polarity query with one majority control (1:1 matching).

    Levels are tried in order across all cases, so exact matches are exhausted before
    any case falls back. Within a level, controls from not-yet-used groups come first,
    then a seeded hash order. The result never depends on input record order.
    """

    def order(query: ReleaseQuery) -> str:
        return digest([seed, query.query_id])

    by_label = {v: sorted([q for q in eligible if q.label == v], key=order) for v in POLARITIES}
    minority: Polarity = min(POLARITIES, key=lambda v: (len(by_label[v]), v))
    cases = by_label[minority]
    controls = by_label["ABSENT" if minority == "PRESENT" else "PRESENT"]
    used: set[str] = set()
    group_use: Counter[str] = Counter()
    matched: dict[str, tuple[ReleaseQuery, int]] = {}
    for level, fields in enumerate(levels):
        pools: dict[tuple[str, ...], list[ReleaseQuery]] = defaultdict(list)
        for control in controls:
            if control.query_id not in used:
                pools[control.key(fields)].append(control)
        for case in cases:
            if case.query_id in matched:
                continue
            pool = [c for c in pools.get(case.key(fields), []) if c.query_id not in used]
            if not pool:
                continue
            control = min(pool, key=lambda c: (group_use[c.group_id], order(c)))
            used.add(control.query_id)
            group_use[control.group_id] += 1
            matched[case.query_id] = (control, level)
    selected: list[ReleaseQuery] = []
    for case in cases:
        if case.query_id not in matched:
            raise ValueError("Too few controls for 1:1 matching; the pool cannot be balanced")
        control, level = matched[case.query_id]
        for query, role, partner in [
            (case, "case", control.query_id),
            (control, "control", case.query_id),
        ]:
            selected.append(
                query.model_copy(
                    update={"match_role": role, "match_partner": partner, "match_level": level}
                )
            )
    surplus = [
        {
            "query_id": c.query_id,
            "reason": "balancing_surplus",
            "group_id": c.group_id,
            "partition": c.partition or "unassigned",
        }
        for c in controls
        if c.query_id not in used
    ]
    return sorted(selected, key=lambda q: q.query_id), surplus


def support(queries: list[ReleaseQuery]) -> dict[str, dict[str, int]]:
    return {
        v: {
            "queries": sum(q.label == v for q in queries),
            "groups": len({q.group_id for q in queries if q.label == v}),
        }
        for v in POLARITIES
    }


def both_polarity_collections(queries: list[ReleaseQuery]) -> list[str]:
    seen: dict[str, set[str]] = defaultdict(set)
    for query in queries:
        seen[query.collection].add(query.label)
    return sorted(c for c, labels in seen.items() if len(labels) == 2)


def grouped_split(
    eligible: list[ReleaseQuery], config: ReleaseConfig
) -> tuple[list[ReleaseQuery], list[dict[str, str]], int, list[dict[str, object]]]:
    """Split the eligible pool by group, then balance each partition by 1:1 matching.

    Seven-fold StratifiedGroupKFold uses (collection, label) strata so every partition
    receives a proportional share of each collection. Matching inside a partition keeps
    every case and its control together without chaining groups across partitions.
    The first seed whose matched partitions pass the support/breadth gates is used.
    """
    ordered = sorted(eligible, key=lambda q: q.query_id)
    strata = [f"{q.collection}|{q.label}" for q in ordered]
    groups = [q.group_id for q in ordered]
    gates = config.min_groups_per_polarity.model_dump()
    attempts: list[dict[str, object]] = []
    for seed in range(config.split_seed_first, config.split_seed_last + 1):
        folds = StratifiedGroupKFold(n_splits=config.folds, shuffle=True, random_state=seed)
        assignment: dict[str, Partition] = {}
        for fold, (_, test) in enumerate(folds.split(ordered, strata, groups)):
            partition: Partition = (
                "test"
                if fold == config.test_fold
                else "validation"
                if fold == config.validation_fold
                else "train"
            )
            for index in test:
                assignment[ordered[index].group_id] = partition
        selected: list[ReleaseQuery] = []
        surplus: list[dict[str, str]] = []
        for name in PARTITIONS:
            rows = [
                q.model_copy(update={"partition": name})
                for q in ordered
                if assignment[q.group_id] == name
            ]
            chosen, extra = matched_selection(rows, config.match_levels, config.seed)
            selected += chosen
            surplus += extra
        summary = {
            name: {
                "eligible": support([q for q in ordered if assignment[q.group_id] == name]),
                "selected": support([q for q in selected if q.partition == name]),
                "both_polarity_collections": both_polarity_collections(
                    [q for q in selected if q.partition == name]
                ),
            }
            for name in PARTITIONS
        }
        passed = all(
            summary[name]["selected"][v]["groups"] >= gates[name]
            and summary[name]["both_polarity_collections"]
            for name in PARTITIONS
            for v in POLARITIES
        )
        attempts.append({"seed": seed, "passed": passed, "partitions": summary})
        if passed:
            return sorted(selected, key=lambda q: q.query_id), surplus, seed, attempts
    raise ValueError("No split seed satisfies the support and breadth gates")


def smartbugs_external(
    queries: list[CandidateQuery], assessments: dict[str, Assessment], sources: dict[str, str]
) -> list[CandidateQuery]:
    """Protected positives with native SmartBugs support and lines on the exact artifact."""
    return [
        q
        for q in sorted(queries, key=lambda q: q.query_id)
        if q.role == "smartbugs_external"
        and q.proposed_verdict == "PRESENT"
        and any(
            sources[assessments[a].artifact_id] == "smartbugs"
            and assessments[a].native_verdict == "PRESENT"
            for a in q.assessment_ids
        )
        and exact_lines(q, assessments)
    ]


def release_statistics(
    eligible: list[ReleaseQuery],
    selected: list[ReleaseQuery],
    exclusions: list[dict[str, str]],
    external: Counter[str],
    external_positives: int,
    seed: int,
    attempts: int,
) -> dict[str, object]:
    def cells(rows: list[ReleaseQuery], field: str) -> list[dict[str, object]]:
        counts: dict[tuple[str, str, str], list[ReleaseQuery]] = defaultdict(list)
        for q in rows:
            counts[q.partition or "unassigned", q.label, getattr(q, field)].append(q)
        return [
            {
                "partition": p,
                "label": v,
                field: value,
                "queries": len(qs),
                "groups": len({q.group_id for q in qs}),
            }
            for (p, v, value), qs in sorted(counts.items())
        ]

    return {
        "state": "final",
        "eligible_pool": support(eligible),
        "eligible_by_collection": cells(eligible, "collection"),
        "selected": support(selected),
        "partitions": {
            name: support([q for q in selected if q.partition == name]) for name in PARTITIONS
        },
        "by_collection": cells(selected, "collection"),
        "by_scope": cells(selected, "scope_kind"),
        "by_pragma": cells(selected, "pragma_minor"),
        "positives_with_vulnerable_lines": {
            name: sum(q.partition == name and bool(q.vulnerable_lines) for q in selected)
            for name in PARTITIONS
        },
        "match_levels": dict(
            sorted(Counter(str(q.match_level) for q in selected if q.match_role == "case").items())
        ),
        "exclusion_reasons": dict(sorted(Counter(e["reason"] for e in exclusions).items())),
        "external_reservations": dict(sorted(external.items())),
        "external_smartbugs_positives": external_positives,
        "split_seed": seed,
        "split_attempts": attempts,
        "notes": [
            "Labels are upstream human annotations (SWC-107 convention), not locally reviewed.",
            "Balancing is 1:1 matched sampling; surplus controls are excluded, not relabeled.",
            "Groups are the inventory components: a conservative superset of release edges.",
            "Pragma is a first-pragma compiler screen, not a deployment date or EVM fork.",
        ],
    }


def build_release(config: ReleaseConfig, root: Path) -> dict[str, object]:
    manifest = verify_manifest(config.inventory_dir)
    if manifest["dataset_content_sha256"] != config.inventory_content_sha256:
        raise ValueError("Inventory content differs from the pinned inventory fingerprint")
    inventory = config.inventory_dir
    queries = read_records(inventory / "queries.parquet", CandidateQuery)
    by_id = {q.query_id: q for q in queries}
    assessments = {
        a.assessment_id: a for a in read_records(inventory / "assessments.parquet", Assessment)
    }
    rows = pq.read_table(
        inventory / "artifacts.parquet", columns=["artifact_id", "source", "code"]
    ).to_pylist()
    sources = {r["artifact_id"]: r["source"] for r in rows}
    codes = {r["artifact_id"]: r["code"] for r in rows}
    taxonomy = json.loads((inventory / "taxonomy.json").read_text(encoding="utf-8"))
    definition = taxonomy["checks"]["REENTRANCY"]["definition"]

    def payload(query: CandidateQuery) -> dict[str, object]:
        result = canonical_payload(
            codes[query.artifact_id], query.check_id, definition, query.scope
        )
        if digest(result) != query.model_input_sha256:
            raise ValueError(f"Stale model input: {query.query_id}")
        return {
            "check_id": result["check_id"],
            "definition": result["definition"],
            "assumptions": result["assumptions"],
            "source": result["source"],
        }

    external = Counter(q.role for q in queries if q.role != "development")
    eligible, exclusions = eligibility(queries, assessments, sources, codes, config)
    logger.info("Eligible upstream-reviewed development queries: %s", len(eligible))
    capped, dropped = cap_group_queries(
        eligible, config.max_queries_per_group_polarity, config.seed
    )
    selected, surplus, seed, attempts = grouped_split(capped, config)
    exclusions += dropped + surplus
    logger.info("Split seed %s after %s attempt(s)", seed, len(attempts))
    externals = smartbugs_external(queries, assessments, sources)
    stats = release_statistics(
        eligible, selected, exclusions, external, len(externals), seed, len(attempts)
    )
    # Surplus controls stay out of every cohort, but their groups keep the assignment.
    group_partitions = sorted(
        {(q.group_id, str(q.partition)) for q in selected}
        | {(e["group_id"], e["partition"]) for e in surplus}
    )
    if len({g for g, _ in group_partitions}) != len(group_partitions):
        raise ValueError("A group was assigned to more than one partition")
    output = config.output_dir
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".release-", dir=output.parent) as temporary:
        stage = Path(temporary)
        for name in PARTITIONS:
            cohort = [
                CohortQuery(**q.model_dump(), **payload(by_id[q.query_id]))
                for q in selected
                if q.partition == name
            ]
            write_records(stage / f"{name}.parquet", cohort, CohortQuery)
        external_rows = [
            ExternalQuery(
                query_id=q.query_id,
                artifact_id=q.artifact_id,
                group_id=str(q.group_id),
                model_input_sha256=q.model_input_sha256,
                label="PRESENT",
                scope_kind=q.scope.kind,
                scope_name=q.scope.name,
                vulnerable_lines=exact_lines(q, assessments),
                **payload(q),
            )
            for q in externals
        ]
        write_records(stage / "external_smartbugs.parquet", external_rows, ExternalQuery)
        write_jsonl(
            stage / "eligible_pool.jsonl",
            [q.model_dump() for q in sorted(eligible, key=lambda q: q.query_id)],
        )
        write_jsonl(
            stage / "release_exclusions.jsonl",
            sorted(exclusions, key=lambda e: (e["query_id"], e["reason"])),
        )
        write_jsonl(
            stage / "split_assignments.jsonl",
            [{"group_id": g, "partition": p} for g, p in group_partitions],
        )
        write_json(stage / "split_attempts.json", attempts)
        write_json(stage / "release_statistics.json", stats)
        write_json(stage / "effective_release_config.json", portable_config(config))
        write_json(stage / "provenance.json", {"project": project_provenance(root)})
        files = {p.name: file_sha256(p) for p in sorted(stage.iterdir())}
        data_files = {k: v for k, v in files.items() if k != "provenance.json"}
        release_manifest = {
            "spec_version": "2.3",
            "state": "final",
            "inventory_content_sha256": config.inventory_content_sha256,
            "release_content_sha256": digest(data_files),
            "files": files,
            "split_seed": seed,
            "counts": {name: stats["partitions"][name] for name in PARTITIONS},
        }
        write_json(stage / "release_manifest.json", release_manifest)
        output.mkdir(exist_ok=True)
        (output / "release_manifest.json").unlink(missing_ok=True)
        for path in sorted(stage.iterdir()):
            if path.name != "release_manifest.json":
                os.replace(path, output / path.name)
        os.replace(stage / "release_manifest.json", output / "release_manifest.json")
    return release_manifest


def portable_config(config: ReleaseConfig) -> dict[str, object]:
    effective = config.model_dump(mode="json")
    effective["inventory_dir"] = "data/processed/inventory"
    effective["output_dir"] = "data/processed/release"
    return effective


def verify_release(directory: Path) -> dict[str, object]:
    manifest = json.loads((directory / "release_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("spec_version") != "2.3":
        raise ValueError("Expected a v2.3 release manifest")
    for name, checksum in manifest["files"].items():
        path = directory / name
        if Path(name).name != name or not path.is_file() or file_sha256(path) != checksum:
            raise ValueError(f"Incomplete or modified release artifact: {name}")
    data_files = {k: v for k, v in manifest["files"].items() if k != "provenance.json"}
    if digest(data_files) != manifest["release_content_sha256"]:
        raise ValueError("Release content fingerprint mismatch")
    return manifest
