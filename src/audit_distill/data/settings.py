"""Strict v2.1 reentrancy data-build settings, separate from retired v1 report/class models."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from audit_distill.config import TokenizerConfig, Upstream
from audit_distill.data.records import Role


class Source(Upstream):
    sparse_paths: list[str]
    role: Role


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    spec_version: Literal["2.1"]
    schema_version: Literal["2.1"]
    active_checks: list[Literal["REENTRANCY"]]
    seed: Literal[42]
    datasets: dict[str, Source]
    tokenizer: TokenizerConfig
    taxonomy_path: Path
    output_dir: Path
    project_directory_aliases: dict[str, str]
    scope_version: Literal["lexical_declarations_v1"]
    skeleton_version: Literal["solidity_skeleton_v2"]
    function_clone_min_tokens: Literal[50]
    near_clone_min_tokens: Literal[100]
    near_clone_length_ratio: Literal[0.8]
    near_clone_jaccard: Literal[0.85]
    cgt_original_collections: list[str]

    @model_validator(mode="after")
    def complete_sources(self) -> "DataConfig":
        if self.active_checks != ["REENTRANCY"]:
            raise ValueError("SPEC v2.1 requires exactly one REENTRANCY check")
        expected = {"dappscan", "smartbugs", "scrubd", "salzano", "cgt", "scbench", "forge"}
        if set(self.datasets) != expected:
            raise ValueError("The seven SPEC v2 source snapshots must be explicit")
        roles = {k: s.role for k, s in self.datasets.items()}
        if roles != {
            k: f"{k}_external" if k in {"smartbugs", "forge"} else "development" for k in expected
        }:
            raise ValueError("Protected external source roles cannot be reassigned")
        return self


REENTRANCY_DEFINITION = (
    "Can an untrusted external call enable re-entry that violates asset/accounting "
    "state invariants before the relevant operation is safely finalized?"
)


def validate_taxonomy(taxonomy: dict[str, object]) -> None:
    """Fail closed on stale registries or silent changes to the locked task."""
    if taxonomy.get("schema_version") != "2.1":
        raise ValueError("Expected a v2.1 taxonomy registry")
    if taxonomy.get("checks") != {
        "REENTRANCY": {
            "family": "REENTRANCY",
            "primary": True,
            "definition": REENTRANCY_DEFINITION,
        }
    }:
        raise ValueError("Taxonomy must contain the exact locked REENTRANCY definition only")
    expected = {
        "swc_candidates": {"107": ["REENTRANCY"]},
        "category_candidates": {"reentrancy": ["REENTRANCY"]},
        "native_candidates": {
            "scrubd:RE": ["REENTRANCY"],
            "scbench:Reentrancy": ["REENTRANCY"],
        },
        "negative_rules": {
            "missing": "UNKNOWN",
            "no_findings": "coverage_review_required",
            "native_negative": "same_property_and_scope_only",
            "non_target_to_reentrancy": "forbidden",
        },
    }
    for table, mapping in expected.items():
        if taxonomy.get(table) != mapping:
            raise ValueError(f"Invalid reentrancy candidate mapping: {table}")


def load_data_config(path: Path, *, root: Path | None = None) -> DataConfig:
    root = (root or path.resolve().parent.parent).resolve()
    config = DataConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    return config.model_copy(
        update={
            "datasets": {
                k: v.model_copy(update={"path": (root / v.path).resolve()})
                for k, v in config.datasets.items()
            },
            "output_dir": (root / config.output_dir).resolve(),
            "taxonomy_path": (root / config.taxonomy_path).resolve(),
        }
    )
