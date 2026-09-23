"""Export the current JSON schemas: v2.1 inventory records and v2.2 release/report records."""

from pathlib import Path

from pydantic import BaseModel

from audit_distill.data.labeling import LabelReview
from audit_distill.data.records import (
    Artifact,
    Assessment,
    CandidateQuery,
    Disagreement,
)
from audit_distill.data.release import ReleaseQuery
from audit_distill.provenance import write_json
from audit_distill.scoped_reports import report_schema


def write_schemas(root: Path) -> None:
    exports: dict[str, list[tuple[str, type[BaseModel]]]] = {
        "v2.1": [
            ("artifact", Artifact),
            ("assessment", Assessment),
            ("candidate_query", CandidateQuery),
            ("disagreement", Disagreement),
        ],
        "v2.2": [("release_query", ReleaseQuery), ("label_review", LabelReview)],
    }
    for version, models in exports.items():
        directory = root / version
        directory.mkdir(parents=True, exist_ok=True)
        for name, model in models:
            schema = model.model_json_schema()
            schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
            write_json(directory / f"{name}.schema.json", schema)
    write_json(root / "v2.2" / "audit_report.schema.json", report_schema())


if __name__ == "__main__":
    write_schemas(Path("schemas"))
