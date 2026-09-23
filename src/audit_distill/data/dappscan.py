"""Strict native DAppSCAN annotation models used by the evidence adapter."""

from pydantic import BaseModel, ConfigDict


class SWCAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    category: str
    function: str
    lineNumber: str


class FileAnnotations(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    filePath: str
    SWCs: list[SWCAnnotation]
