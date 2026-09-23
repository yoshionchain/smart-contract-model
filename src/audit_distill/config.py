"""Shared immutable upstream and tokenizer configuration types."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Upstream(ConfigModel):
    repository: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: Path


class TokenizerConfig(ConfigModel):
    model_id: Literal["Qwen/Qwen2.5-Coder-1.5B-Instruct"]
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    max_code_tokens: Literal[6000]
    max_sequence_tokens: Literal[8192]
    max_report_tokens: Literal[480]
