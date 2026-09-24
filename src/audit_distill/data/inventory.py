"""Reproducible reentrancy candidate inventory over all pinned sources."""

import csv
import json
import logging
import os
import re
import tempfile
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from pydantic import BaseModel

from audit_distill.data import forge, ingest, native
from audit_distill.data.baseline import baseline_statistics
from audit_distill.data.candidates import candidates, canonical_payload
from audit_distill.data.comments import strip_comments
from audit_distill.data.fetch import verify_checkout
from audit_distill.data.groups import build_groups
from audit_distill.data.ledger import Ledger
from audit_distill.data.records import Artifact, Assessment, CandidateQuery, Record
from audit_distill.data.scopes import digest
from audit_distill.data.settings import DataConfig
from audit_distill.provenance import file_sha256, git_output, project_provenance, write_json

logger = logging.getLogger(__name__)


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_records(path: Path, rows: Sequence[BaseModel], model: type[BaseModel]) -> None:
    """Explicit Arrow schemas keep empty/small fixture datasets readable too."""
    schema = model.model_json_schema()
    definitions = schema.get("$defs", {})

    def arrow_type(field: dict[str, object]) -> pa.DataType:
        if "$ref" in field:
            return arrow_type(definitions[field["$ref"].rsplit("/", 1)[1]])
        if "anyOf" in field:
            return arrow_type(next(f for f in field["anyOf"] if f.get("type") != "null"))
        kind = field.get("type")
        if kind == "string":
            return pa.string()
        if kind == "integer":
            return pa.int64()
        if kind == "boolean":
            return pa.bool_()
        if kind == "array":
            return pa.list_(arrow_type(field["items"]))
        if kind == "object":
            if "properties" not in field:
                return pa.map_(pa.string(), pa.string())
            return pa.struct(
                [(name, arrow_type(value)) for name, value in field["properties"].items()]
            )
        raise ValueError(f"Unsupported record field: {field}")

    table = pa.Table.from_pylist(
        [r.model_dump() for r in rows], schema=pa.schema(list(arrow_type(schema)))
    )
    pq.write_table(table, path, compression="zstd")


def read_records(path: Path, model: type[Record]) -> list[Record]:
    rows = pq.read_table(path).to_pylist()
    for row in rows:
        if "metadata" in row:
            row["metadata"] = dict(row["metadata"])
    return [model.model_validate(row) for row in rows]


def verify_inventory(config: DataConfig) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, source in config.datasets.items():
        state = verify_checkout(source)
        tracked = [
            p
            for p in git_output(source.path, "ls-tree", "-r", "-z", "--name-only", "HEAD").split(
                "\0"
            )
            if p
        ]
        selected = [
            p
            for p in tracked
            if "/" not in p or any(p == s or p.startswith(s + "/") for s in source.sparse_paths)
        ]
        missing = [p for p in selected if not (source.path / p).is_file()]
        if missing:
            raise ValueError(f"Incomplete {name} checkout: {missing[:5]}; rerun fetch_data.py")
        result[name] = state | {
            "selected_file_count": len(selected),
            "selected_paths_sha256": digest(selected),
            "license_notices": {
                p: file_sha256(source.path / p)
                for p in selected
                if re.match(r"(?i)^(license|licence|copying|notice)(\.|$)", Path(p).name)
            },
        }
    return result


def verify_manifest(directory: Path) -> dict[str, object]:
    """Verify an inventory's version, file hashes and content fingerprint."""
    manifest = json.loads((directory / "dataset_manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("spec_version") != "2.3"
        or manifest.get("schema_version") != "2.3"
        or manifest.get("active_checks") != ["REENTRANCY"]
        or manifest.get("state") != "inventory"
    ):
        raise ValueError("Expected a v2.3 reentrancy inventory manifest")
    for name, checksum in manifest["files"].items():
        path = directory / name
        if Path(name).name != name or not path.is_file() or file_sha256(path) != checksum:
            raise ValueError(f"Incomplete or modified inventory artifact: {name}")
    data_files = {k: v for k, v in manifest["files"].items() if k != "provenance.json"}
    if digest(data_files) != manifest["dataset_content_sha256"]:
        raise ValueError("Inventory content fingerprint mismatch")
    return manifest


def statistics(
    ledger: Ledger,
    queries: list[CandidateQuery],
    groups: list[dict[str, object]],
    conflicts: list[Record],
    exclusions: list[dict[str, str]],
    edges: list[dict[str, object]],
) -> dict[str, object]:
    artifacts = list(ledger.artifacts.values())
    cells: dict[tuple[str, str, str], list[CandidateQuery]] = defaultdict(list)
    ancestry_cells: dict[tuple[str, str, str, str, str], list[CandidateQuery]] = defaultdict(list)
    for q in queries:
        cells[q.role, q.check_id, q.proposed_verdict].append(q)
        for collection in q.original_collections:
            ancestry_cells[q.role, collection, q.check_id, q.proposed_verdict, q.scope.kind].append(
                q
            )
    compiler_eras: Counter[str] = Counter()
    by_identity = {a.code_identity_sha256: a for a in artifacts}
    for identity in sorted({q.code_identity_sha256 for q in queries}):
        art = by_identity[identity]
        match = re.search(r"\bpragma\s+solidity\b[^;]*?(0\.\d+)", art.code)
        compiler_eras[match[1] if match else "unspecified"] += 1
    return {
        "state": "inventory",
        "baseline": baseline_statistics(ledger.artifacts, ledger.assessments, queries),
        "training_ready_queries": 0,
        "human_reviews": 0,
        "source_artifacts": len(artifacts),
        "native_assessments": len(ledger.assessments),
        "assessments_without_target_mapping": sum(
            not a.candidate_checks for a in ledger.assessments
        ),
        "assessments_supporting_candidates": len({a for q in queries for a in q.assessment_ids}),
        "artifacts_without_native_assessments": len(
            set(ledger.artifacts) - {a.artifact_id for a in ledger.assessments}
        ),
        "lexical_identities": len(
            {a.code_identity_sha256 for a in artifacts if a.code_identity_sha256}
        ),
        "unreadable_artifacts": sum(a.code_identity_sha256 is None for a in artifacts),
        "artifacts_by_source": dict(sorted(Counter(a.source for a in artifacts).items())),
        "assessments_by_source": dict(
            sorted(
                Counter(ledger.artifacts[a.artifact_id].source for a in ledger.assessments).items()
            )
        ),
        "native_verdicts": dict(
            sorted(Counter(a.native_verdict for a in ledger.assessments).items())
        ),
        "candidate_queries": len(queries),
        "candidate_source_compiler_eras_first_pragma": dict(sorted(compiler_eras.items())),
        "candidate_roles": dict(sorted(Counter(q.role for q in queries).items())),
        "candidate_cells": [
            {
                "role": role,
                "check_id": check,
                "proposed_verdict": verdict,
                "queries": len(rows),
                "source_identities": len({q.code_identity_sha256 for q in rows}),
                "groups": len({q.group_id for q in rows}),
            }
            for (role, check, verdict), rows in sorted(cells.items())
        ],
        "disagreements": len(conflicts),
        "original_collection_cells": [
            {
                "role": role,
                "original_collection": collection,
                "check_id": check,
                "proposed_verdict": verdict,
                "scope_kind": scope,
                "queries": len(rows),
                "groups": len({q.group_id for q in rows}),
            }
            for (role, collection, check, verdict, scope), rows in sorted(ancestry_cells.items())
        ],
        "assessment_evidence_tiers": dict(
            sorted(Counter(a.evidence_tier for a in ledger.assessments).items())
        ),
        "disputed_identities": len({c.code_identity_sha256 for c in conflicts}),
        "assessment_exclusion_reasons": dict(
            sorted(Counter(e["reason"] for e in exclusions).items())
        ),
        "ingestion_issue_reasons": dict(
            sorted(Counter(e["reason"] for e in ledger.ingestion_issues).items())
        ),
        "review_flags": dict(
            sorted(Counter(f for q in queries for f in q.review_required).items())
        ),
        "groups": len(groups),
        "group_roles": dict(sorted(Counter(g["role"] for g in groups).items())),
        "active_group_edges": sum(e["active"] for e in edges),
        "inactive_raw_matches": sum(not e["active"] for e in edges),
        "largest_groups": [
            {
                "group_id": g["group_id"],
                "role": g["role"],
                "source_identities": len(g["code_identities"]),
            }
            for g in sorted(groups, key=lambda g: (-len(g["code_identities"]), g["group_id"]))[:20]
        ],
        "project_independence_verified": False,
    }


def validate_foundation(
    ledger: Ledger, queries: list[CandidateQuery], groups: list[dict[str, object]]
) -> None:
    assessments = {a.assessment_id: a for a in ledger.assessments}
    if len(assessments) != len(ledger.assessments):
        raise ValueError("Duplicate assessment IDs")
    if len({q.query_id for q in queries}) != len(queries):
        raise ValueError("Duplicate query IDs")
    memberships: dict[str, tuple[str, str]] = {}
    projects: dict[str, str] = {}
    for group in groups:
        for key in group["known_project_keys"]:
            if key in projects and projects[key] != group["group_id"]:
                raise ValueError("Known project belongs to multiple groups")
            projects[key] = group["group_id"]
        for identity in group["code_identities"]:
            if identity in memberships:
                raise ValueError("Identity belongs to multiple groups")
            memberships[identity] = (group["group_id"], group["role"])
    for artifact in ledger.artifacts.values():
        if artifact.role != "development" and artifact.code_identity_sha256:
            membership = memberships.get(artifact.code_identity_sha256)
            if membership is None or membership[1] == "development":
                raise ValueError("Protected source escaped external reservation")
    for query in queries:
        artifact = ledger.artifacts[query.artifact_id]
        if not query.assessment_ids or any(a not in assessments for a in query.assessment_ids):
            raise ValueError("Candidate missing native evidence")
        if artifact.code_identity_sha256 != query.code_identity_sha256:
            raise ValueError("Candidate/source identity mismatch")
        if memberships.get(query.code_identity_sha256) != (query.group_id, query.role):
            raise ValueError("Candidate group or role mismatch")
        if (
            artifact.code_tokens is None
            or artifact.code_tokens > ledger.config.tokenizer.max_code_tokens
        ):
            raise ValueError("Candidate violates source token budget")
        if strip_comments(artifact.code) != artifact.code:
            raise ValueError("Candidate contains unsanitized comments")
        for aid in query.assessment_ids:
            native = assessments[aid]
            if native.native_verdict == "UNKNOWN" or query.check_id not in native.candidate_checks:
                raise ValueError("Candidate lacks a known native check judgment")
            if (
                ledger.artifacts[native.artifact_id].code_identity_sha256
                != query.code_identity_sha256
            ):
                raise ValueError("Candidate support is for a different source identity")
        payload = canonical_payload(
            artifact.code,
            query.check_id,
            ledger.taxonomy["checks"][query.check_id]["definition"],
            query.scope,
        )
        if digest(payload) != query.model_input_sha256:
            raise ValueError("Stale model input hash")


def publish(
    config: DataConfig,
    ledger: Ledger,
    queries: list[CandidateQuery],
    groups: list[dict[str, object]],
    edges: list[dict[str, object]],
    conflicts: list[Record],
    exclusions: list[dict[str, str]],
    provenance: dict[str, object],
) -> dict[str, object]:
    output = config.output_dir
    manifest_path = output / "dataset_manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            previous.get("spec_version") != config.spec_version
            or previous.get("schema_version") != config.schema_version
            or previous.get("active_checks") != config.active_checks
        ):
            raise ValueError(
                "Refusing to overwrite an incompatible baseline; choose a new directory"
            )
    if (output / "dataset_freeze.json").exists():
        raise ValueError("Refusing to overwrite a frozen dataset; choose a new output directory")
    if any(
        (output / f"{name}.parquet").exists()
        for name in ["train", "validation", "test", "test_primary", "test_secondary"]
    ):
        raise ValueError("Choose a separate inventory output directory; split files already exist")
    validate_foundation(ledger, queries, groups)
    queries = sorted(queries, key=lambda q: q.query_id)
    groups = sorted(groups, key=lambda g: g["group_id"])
    conflicts = sorted(conflicts, key=lambda c: c.disagreement_id)
    exclusions = sorted(exclusions, key=lambda row: json.dumps(row, sort_keys=True))
    edges = sorted(edges, key=lambda row: json.dumps(row, sort_keys=True))
    output.parent.mkdir(parents=True, exist_ok=True)
    stats = statistics(ledger, queries, groups, conflicts, exclusions, edges)
    with tempfile.TemporaryDirectory(prefix=".v2-build-", dir=output.parent) as temporary:
        stage = Path(temporary)
        write_records(
            stage / "artifacts.parquet",
            sorted(ledger.artifacts.values(), key=lambda a: a.artifact_id),
            Artifact,
        )
        write_records(
            stage / "assessments.parquet",
            sorted(ledger.assessments, key=lambda a: a.assessment_id),
            Assessment,
        )
        write_records(stage / "queries.parquet", queries, CandidateQuery)
        write_jsonl(stage / "exclusions.jsonl", exclusions)
        write_jsonl(stage / "conflicts.jsonl", [c.model_dump() for c in conflicts])
        write_jsonl(stage / "group_edges.jsonl", edges)
        write_jsonl(stage / "groups.jsonl", groups)
        write_jsonl(
            stage / "ingestion_issues.jsonl",
            sorted(ledger.ingestion_issues, key=lambda row: json.dumps(row, sort_keys=True)),
        )
        write_json(stage / "taxonomy.json", ledger.taxonomy)
        write_json(stage / "dataset_statistics.json", stats)
        with (stage / "dataset_statistics.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "role",
                    "check_id",
                    "proposed_verdict",
                    "queries",
                    "source_identities",
                    "groups",
                ],
            )
            writer.writeheader()
            writer.writerows(stats["candidate_cells"])
        effective = config.model_dump(mode="json")
        for name in effective["datasets"]:
            effective["datasets"][name]["path"] = f"data/raw/{name}"
        effective["output_dir"] = "data/processed/inventory"
        effective["taxonomy_path"] = "configs/taxonomy.yaml"
        write_json(stage / "effective_config.json", effective)
        write_json(stage / "provenance.json", provenance)
        files = {p.name: file_sha256(p) for p in sorted(stage.iterdir())}
        data_files = {k: v for k, v in files.items() if k != "provenance.json"}
        manifest = {
            "spec_version": config.spec_version,
            "schema_version": config.schema_version,
            "active_checks": config.active_checks,
            "state": "inventory",
            "training_ready": False,
            "dataset_content_sha256": digest(data_files),
            "files": files,
            "counts": {
                k: stats[k]
                for k in [
                    "source_artifacts",
                    "native_assessments",
                    "candidate_queries",
                    "groups",
                    "training_ready_queries",
                ]
            },
            "next_stage": "release (build_dataset.py --stage release)",
            "teacher_generation_run": False,
            "training_run": False,
        }
        write_json(stage / "dataset_manifest.json", manifest)
        output.mkdir(exist_ok=True)
        (output / "dataset_manifest.json").unlink(missing_ok=True)
        for path in sorted(stage.iterdir()):
            if path.name != "dataset_manifest.json":
                os.replace(path, output / path.name)
        os.replace(stage / "dataset_manifest.json", output / "dataset_manifest.json")
    return manifest


def build_inventory(config: DataConfig, root: Path) -> dict[str, object]:
    from transformers import AutoTokenizer

    upstreams = verify_inventory(config)
    taxonomy = yaml.safe_load(config.taxonomy_path.read_text(encoding="utf-8"))
    ledger = Ledger(config, taxonomy)
    for name, adapter in [
        ("dappscan", ingest.dappscan),
        ("smartbugs", ingest.smartbugs),
        ("scrubd", native.scrubd),
        ("salzano", ingest.salzano),
        ("cgt", native.cgt),
        ("scbench", native.scbench),
        ("forge", forge.forge),
    ]:
        logger.info("Reading pinned %s sources and native evidence", name)
        adapter(ledger)
        if not any(a.source == name for a in ledger.artifacts.values()):
            raise ValueError(f"No source artifacts were ingested for {name}")
        if not any(ledger.artifacts[a.artifact_id].source == name for a in ledger.assessments):
            raise ValueError(f"No native assessments were ingested for {name}")
        logger.info(
            "Inventory now has %s artifacts and %s assessments",
            len(ledger.artifacts),
            len(ledger.assessments),
        )
    if len({a.assessment_id for a in ledger.assessments}) != len(ledger.assessments):
        raise ValueError("Duplicate native assessment IDs")
    logger.info("Loading pinned tokenizer; no model weights or teacher calls")
    tokenizer = AutoTokenizer.from_pretrained(
        config.tokenizer.model_id, revision=config.tokenizer.revision, trust_remote_code=False
    )

    def count_tokens(code: str) -> int:
        return len(
            tokenizer.encode(code, add_special_tokens=False, truncation=False, verbose=False)
        )

    queries, conflicts, exclusions = candidates(ledger, count_tokens)
    logger.info("Grouping %s mechanically resolved candidates", len(queries))
    groups, edges = build_groups(list(ledger.artifacts.values()), queries, config)
    if verify_inventory(config) != upstreams:
        raise ValueError("Upstream inventory changed during the build")
    provenance = {
        "built_at_utc": datetime.now(UTC).isoformat(),
        "upstreams": upstreams,
        "project": project_provenance(root),
        "tokenizer": {
            "class": type(tokenizer).__name__,
            "backend_sha256": digest(tokenizer.backend_tokenizer.to_str()),
            "revision": config.tokenizer.revision,
            "truncation": False,
        },
        "source_paths": {k: str(s.path) for k, s in config.datasets.items()},
    }
    manifest = publish(config, ledger, queries, groups, edges, conflicts, exclusions, provenance)
    logger.info("Published inventory: %s", config.output_dir)
    return manifest
