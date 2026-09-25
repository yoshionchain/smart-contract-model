"""Strict data-build settings (dataset version 3.0)."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from audit_distill.config import ConfigModel, TokenizerConfig, Upstream


class Source(Upstream):
    sparse_paths: list[str]


class Gates(ConfigModel):
    train: int = Field(ge=1)
    validation: int = Field(ge=1)
    test: int = Field(ge=1)


class DataConfig(ConfigModel):
    version: Literal["3.0"]
    source: Source
    tokenizer: TokenizerConfig
    output_dir: Path
    manifest_dir: Path
    check_id: Literal["REENTRANCY"]
    definition: str
    assumptions: list[str] = Field(min_length=1)
    excluded_origins: list[str]
    label_leak_pattern: str
    near_clone_min_tokens: int
    near_clone_length_ratio: float
    near_clone_jaccard: float
    seed: int
    match_levels: list[list[Literal["pragma_minor"]]]
    folds: int = Field(ge=3)
    test_folds: list[int]
    validation_folds: list[int]
    split_seed_first: int
    split_seed_last: int
    min_groups_per_polarity: Gates

    @model_validator(mode="after")
    def consistent(self) -> "DataConfig":
        if not self.match_levels or self.match_levels[-1] != []:
            raise ValueError("Matching must end with the catch-all level []")
        held_out = self.test_folds + self.validation_folds
        if len(set(held_out)) != len(held_out) or not all(0 <= f < self.folds for f in held_out):
            raise ValueError("Test and validation folds must be distinct, valid fold numbers")
        return self


def load_data_config(path: Path) -> DataConfig:
    """Load the config; relative paths are resolved against the repository root."""
    root = path.resolve().parent.parent
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["source"]["path"] = root / data["source"]["path"]
    for key in ("output_dir", "manifest_dir"):
        data[key] = root / data[key]
    return DataConfig.model_validate(data)
