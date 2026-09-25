"""Export the report schema and the teacher answer schema."""

import json
from pathlib import Path

from audit_distill.provenance import write_json
from audit_distill.scoped_reports import report_schema, teacher_schema

if __name__ == "__main__":
    write_json(Path("schemas/audit_report.schema.json"), report_schema())
    # Unsorted on purpose: key order is the order in which the teacher generates fields.
    Path("schemas/teacher_answer.schema.json").write_text(
        json.dumps(teacher_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
