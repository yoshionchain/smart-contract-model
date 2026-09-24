"""Validate a persisted candidate baseline without certifying human labels."""

import argparse
import json
from pathlib import Path

from audit_distill.data.identity import code_identity
from audit_distill.data.inventory import (
    read_records,
    statistics,
    validate_foundation,
    verify_manifest,
)
from audit_distill.data.ledger import Ledger
from audit_distill.data.line_numbers import render_line_numbers, source_lines
from audit_distill.data.normalize import normalize_for_hash, sha256_text
from audit_distill.data.records import Artifact, Assessment, CandidateQuery, Disagreement
from audit_distill.data.settings import DataConfig
from audit_distill.provenance import write_json


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def validate_baseline(directory: Path) -> dict[str, object]:
    manifest = verify_manifest(directory)
    config = DataConfig.model_validate_json((directory / "effective_config.json").read_text())
    taxonomy = json.loads((directory / "taxonomy.json").read_text())
    ledger = Ledger(config, taxonomy)
    artifacts = read_records(directory / "artifacts.parquet", Artifact)
    ledger.artifacts = {a.artifact_id: a for a in artifacts}
    if len(ledger.artifacts) != len(artifacts):
        raise ValueError("Duplicate artifact IDs")
    ledger.assessments = read_records(directory / "assessments.parquet", Assessment)
    if any(a.artifact_id not in ledger.artifacts for a in ledger.assessments):
        raise ValueError("Native evidence references a missing artifact")
    ledger.ingestion_issues = read_jsonl(directory / "ingestion_issues.jsonl")
    queries = read_records(directory / "queries.parquet", CandidateQuery)
    groups = read_jsonl(directory / "groups.jsonl")
    edges = read_jsonl(directory / "group_edges.jsonl")
    conflicts = [
        Disagreement.model_validate(row) for row in read_jsonl(directory / "conflicts.jsonl")
    ]
    exclusions = read_jsonl(directory / "exclusions.jsonl")
    validate_foundation(ledger, queries, groups)
    for artifact in artifacts:
        if artifact.code_identity_sha256 is None:
            continue
        if (
            code_identity(artifact.code) != artifact.code_identity_sha256
            or sha256_text(normalize_for_hash(artifact.code)) != artifact.code_sha256
            or sha256_text(render_line_numbers(artifact.code)) != artifact.source_input_sha256
            or len(source_lines(artifact.code)) != artifact.line_count
        ):
            raise ValueError(f"Stale source identity/coordinates: {artifact.artifact_id}")
    expected = statistics(ledger, queries, groups, conflicts, exclusions, edges)
    if json.loads((directory / "dataset_statistics.json").read_text()) != expected:
        raise ValueError("Baseline statistics do not match persisted records")
    if manifest["counts"] != {key: expected[key] for key in manifest["counts"]}:
        raise ValueError("Manifest counts do not match persisted records")
    if manifest.get("training_ready") is not False or any(q.training_ready for q in queries):
        raise ValueError("Candidate inventory cannot certify training readiness")
    return {
        "spec_version": config.spec_version,
        "schema_version": config.schema_version,
        "active_checks": config.active_checks,
        "dataset_content_sha256": manifest["dataset_content_sha256"],
        "mechanical_validation": "PASS",
        "validated_file_count": len(manifest["files"]),
        "counts": manifest["counts"],
        "human_label_validation": "PENDING",
        "split_support_gates": "NOT_RUN",
        "training_ready": False,
        "checks": [
            "manifest hashes and version compatibility",
            "typed records and evidence references",
            "source identities, line counts and exact model input hashes",
            "candidate token budgets and comment sanitization",
            "group membership, known-project isolation and external reservations",
            "recomputed statistics",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/processed/inventory"))
    parser.add_argument("--output", type=Path, help="Optional small validation report")
    args = parser.parse_args()
    try:
        # Never let a report overwrite its own validated input.
        if args.output and args.output.resolve().is_relative_to(args.dataset.resolve()):
            raise ValueError("Write validation reports outside the baseline artifact directory")
        result = validate_baseline(args.dataset)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Baseline validation stopped: {error}\n")
