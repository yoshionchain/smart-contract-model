"""Append source-linked evidence without converting missing labels into negatives."""

import hashlib
from pathlib import Path

from audit_distill.data.comments import strip_comments
from audit_distill.data.identity import code_identity
from audit_distill.data.line_numbers import render_line_numbers, source_lines
from audit_distill.data.normalize import normalize_for_hash, sha256_text
from audit_distill.data.records import Artifact, Assessment, Check, Verdict
from audit_distill.data.scopes import digest
from audit_distill.data.settings import DataConfig, validate_taxonomy


class Ledger:
    def __init__(self, config: DataConfig, taxonomy: dict[str, object]) -> None:
        validate_taxonomy(taxonomy)
        self.config = config
        self.taxonomy = taxonomy
        self.artifacts: dict[str, Artifact] = {}
        self.assessments: list[Assessment] = []
        self.annotation_hashes: dict[Path, str] = {}
        self.ingestion_issues: list[dict[str, str]] = []

    def artifact(
        self,
        source: str,
        path: str,
        raw: bytes,
        *,
        collection: str = "",
        project_keys: list[str] | None = None,
        role: str | None = None,
    ) -> Artifact:
        upstream = self.config.datasets[source]
        key = digest([source, upstream.revision, path])
        record = Artifact(
            artifact_id=key,
            source=source,
            revision=upstream.revision,
            path=path,
            original_collection=collection or source,
            role=role or upstream.role,
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            project_keys=sorted(set(project_keys or [])),
            ancestry_known=False,
        )
        try:
            original = raw.decode("utf-8")
            if not original.strip() or "\x00" in original:
                raise ValueError("Empty or non-text source")
            clean = strip_comments(original)
            if len(clean) != len(original) or [
                (i, x) for i, x in enumerate(original) if x in "\r\n"
            ] != [(i, x) for i, x in enumerate(clean) if x in "\r\n"]:
                raise ValueError("Comment removal changed coordinates")
            record.code_identity_sha256 = code_identity(clean)
            record.code = clean
            record.code_sha256 = sha256_text(normalize_for_hash(clean))
            record.source_input_sha256 = sha256_text(render_line_numbers(clean))
            record.line_count = len(source_lines(clean))
        except (UnicodeError, ValueError) as error:
            record.issues = [f"unreadable_source:{error}"]
        previous = self.artifacts.get(key)
        if previous is not None:
            if previous.model_dump() != record.model_dump():
                raise ValueError(f"Conflicting artifact link: {source}:{path}")
            return previous
        self.artifacts[key] = record
        return record

    def file(self, source: str, path: Path, **kwargs: object) -> Artifact:
        root = self.config.datasets[source].path
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Source path escapes checkout: {path}")
        return self.artifact(source, path.relative_to(root).as_posix(), path.read_bytes(), **kwargs)

    def assess(
        self,
        artifact: Artifact,
        *,
        annotation: Path,
        native_id: str,
        prop: str,
        verdict: Verdict,
        kind: str = "FILE",
        scope: str = "FILE",
        checks: list[Check] | None = None,
        lines: list[int] | None = None,
        rationale: str = "",
        metadata: dict[str, str] | None = None,
        issues: list[str] | None = None,
        reviewed: bool = True,
        reference: str = "",
    ) -> None:
        from audit_distill.provenance import file_sha256

        root = self.config.datasets[artifact.source].path
        if annotation not in self.annotation_hashes:
            self.annotation_hashes[annotation] = file_sha256(annotation)
        native_lines = sorted(set(lines or []))
        flags = list(issues or [])
        if any(n < 1 or n > artifact.line_count for n in native_lines):
            flags.append("annotation_line_out_of_bounds")
        self.assessments.append(
            Assessment(
                assessment_id=digest(
                    [
                        artifact.artifact_id,
                        annotation.relative_to(root).as_posix(),
                        native_id,
                        prop,
                        kind,
                        scope,
                    ]
                ),
                artifact_id=artifact.artifact_id,
                annotation_path=annotation.relative_to(root).as_posix(),
                annotation_sha256=self.annotation_hashes[annotation],
                native_id=native_id,
                native_property=prop,
                native_verdict=verdict,
                native_scope_kind=kind,
                native_scope=scope,
                candidate_checks=checks or [],
                evidence_tier="UPSTREAM_REVIEWED" if reviewed else "UNVERIFIED",
                evidence_reference=reference,
                native_lines=native_lines,
                rationale=rationale,
                metadata=metadata or {},
                issues=sorted(set(flags)),
            )
        )

    def mapping(self, table: str, key: str) -> list[Check]:
        mapping = self.taxonomy[table]
        if not isinstance(mapping, dict):
            raise ValueError(f"Invalid taxonomy table: {table}")
        return list(mapping.get(key, []))
