"""Strict native SmartBugs metadata models; ingestion keeps annotations separate."""

from pydantic import BaseModel, ConfigDict, Field


class Vulnerability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    category: str
    lines: list[int]


class SmartBugsEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    path: str
    pragma: str | list[str] | None = None
    source: str | None = None
    vulnerabilities: list[Vulnerability] = Field(min_length=1)
