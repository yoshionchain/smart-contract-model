"""FORGE evidence stays external and unverified until exact-audit revision review."""

import json
import re
from pathlib import Path

from audit_distill.data.ingest import parse_lines
from audit_distill.data.ledger import Ledger
from audit_distill.data.projects import repository_keys
from audit_distill.provenance import file_sha256


def strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    return []


def forge(ledger: Ledger) -> None:
    root = ledger.config.datasets["forge"].path
    for path in sorted((root / "dataset-curated/findings-without-source").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        ledger.ingestion_issues.append(
            {
                "source": "forge",
                "native_id": path.relative_to(root).as_posix(),
                "reason": "audit_report_without_source",
                "annotation_sha256": file_sha256(path),
                "findings_count": str(len(document["findings"])),
            }
        )
    reports: dict[str, list[dict[str, object]]] = {}
    for path in sorted((root / "dataset-curated/findings").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        name = Path(str(document.get("path", ""))).name
        reports.setdefault(name, []).append(document)
    for path in sorted((root / "flatten/vfp").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        name = doc["project_name"]
        keys = {f"forge-report:{name}"}
        audit_info = reports.get(name, [])
        for report in audit_info:
            for url in strings(report.get("project_info", {})):
                keys.update(repository_keys(url))
        for filename, code in sorted(doc["affected_files"].items()):
            if not isinstance(code, str):
                raise ValueError(f"Invalid FORGE source payload: {path}:{filename}")
            art = ledger.artifact(
                "forge",
                f"{path.relative_to(root).as_posix()}#file={filename}",
                code.encode(),
                project_keys=sorted(keys),
            )
            art.ancestry_known = any(k.startswith("github.com/") for k in keys)
            linked = False
            for finding in doc["findings"]:
                files = strings(finding.get("files", []))
                if (
                    files
                    and filename not in files
                    and Path(filename).name not in {Path(f).name for f in files}
                ):
                    continue
                linked = True
                link_flags = []
                if not files:
                    link_flags.append("missing_finding_file_link")
                elif (
                    filename not in files
                    and sum(Path(f).name == Path(filename).name for f in doc["affected_files"]) > 1
                ):
                    link_flags.append("ambiguous_finding_file_link")
                categories = strings(finding.get("category", {}))
                text = " ".join(strings([finding.get("title", ""), finding.get("description", "")]))
                checks = set()
                if re.search(r"\bre[ -]?entr(?:ancy|ant)\b", text, re.I):
                    checks.add("REENTRANCY")
                native_lines = []
                locations = strings(finding.get("location", []))
                for loc in locations:
                    if Path(filename).name in loc and "#" in loc:
                        lines, _ = parse_lines(loc.rsplit("#", 1)[1])
                        native_lines.extend(lines)
                ledger.assess(
                    art,
                    annotation=path,
                    native_id=str(finding["id"]),
                    prop="|".join(sorted(categories)) or "unmapped_audit_finding",
                    verdict="PRESENT",
                    checks=sorted(checks),
                    lines=native_lines,
                    rationale=text,
                    reviewed=False,
                    issues=[
                        "exact_audited_revision_unverified",
                        "audit_scope_unverified",
                        *link_flags,
                    ],
                    metadata={
                        "project_report": name,
                        "native_locations": json.dumps(locations),
                        "audit_metadata": json.dumps(
                            [r.get("project_info", {}) for r in audit_info], sort_keys=True
                        ),
                    },
                    reference="https://github.com/shenyimings/FORGE-Curated",
                )
            if not linked:
                ledger.ingestion_issues.append(
                    {
                        "source": "forge",
                        "native_id": art.path,
                        "reason": "no_exact_finding_file_link",
                    }
                )
