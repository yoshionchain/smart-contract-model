"""Versioned evidence records. A candidate verdict is never a certified training label."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Check = Literal["REENTRANCY"]
Verdict = Literal["PRESENT", "ABSENT", "UNKNOWN"]
Role = Literal["development", "smartbugs_external", "forge_external"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["2.1"] = "2.1"


class Artifact(Record):
    artifact_id: str
    source: str
    revision: str
    path: str
    original_collection: str
    role: Role
    raw_sha256: str
    code_sha256: str | None = None
    code_identity_sha256: str | None = None
    source_input_sha256: str | None = None
    code: str = ""
    line_count: int = 0
    code_tokens: int | None = None
    project_keys: list[str] = Field(default_factory=list)
    ancestry_known: bool = False
    issues: list[str] = Field(default_factory=list)


class Assessment(Record):
    assessment_id: str
    artifact_id: str
    annotation_path: str
    annotation_sha256: str
    native_id: str
    native_property: str
    native_verdict: Verdict
    native_scope_kind: Literal["FILE", "CONTRACT", "FUNCTION"]
    native_scope: str
    candidate_checks: list[Check]
    evidence_tier: Literal["UPSTREAM_REVIEWED", "UNVERIFIED"]
    evidence_reference: str
    native_lines: list[int] = Field(default_factory=list)
    rationale: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class Scope(Record):
    kind: Literal["FILE", "CONTRACT", "FUNCTION"]
    name: str
    start_line: int
    end_line: int
    start_token: int
    end_token: int
    token_identity: str


class CandidateQuery(Record):
    query_id: str
    artifact_id: str
    assessment_ids: list[str]
    code_identity_sha256: str
    check_id: Check
    scope: Scope
    native_verdicts: list[Verdict]
    proposed_verdict: Verdict
    role: Role
    original_collections: list[str]
    group_id: str | None = None
    mechanical_status: Literal["PASS", "EXCLUDED"]
    issues: list[str]
    review_required: list[str]
    training_ready: Literal[False] = False
    model_input_sha256: str


class Disagreement(Record):
    disagreement_id: str
    code_identity_sha256: str
    check_id: Check
    assessment_ids: list[str]
    kind: Literal["same_property_conflict", "cross_property_disagreement"]
    status: Literal["UNRESOLVED"] = "UNRESOLVED"
