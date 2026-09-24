"""Export the semantic report JSON schema (used to constrain teacher output)."""

from pathlib import Path

from audit_distill.provenance import write_json
from audit_distill.scoped_reports import report_schema

if __name__ == "__main__":
    write_json(Path("schemas/audit_report.schema.json"), report_schema())
