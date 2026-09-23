"""Pinned DAppSCAN, SmartBugs and corrected Salzano evidence adapters."""

import csv
import json
import re
from collections import defaultdict

from tqdm import tqdm

from audit_distill.data.dappscan import FileAnnotations
from audit_distill.data.io import contained_path
from audit_distill.data.ledger import Ledger
from audit_distill.data.projects import load_project_groups
from audit_distill.data.records import Artifact
from audit_distill.data.smartbugs import SmartBugsEntry


def deployment_key(address: str, chain: str = "ethereum-main") -> list[str]:
    if re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
        return [f"deployment:{chain}:{address.lower()}"]
    return []


def parse_lines(value: str) -> tuple[list[int], list[str]]:
    if value.strip().lower() in {"", "n/a", "na", "none", "all"}:
        return [], []
    normalized = re.sub(r"[Ll]", "", value).replace("，", ",")
    found: set[int] = set()
    for part in re.split(r"[,;\s]+", normalized.strip()):
        match = re.fullmatch(r"(\d+)(?:[-–](\d+))?", part)
        if not match:
            return [], ["unparsed_native_location"]
        low, high = int(match[1]), int(match[2] or match[1])
        if high < low or high - low > 100_000:
            return [], ["unparsed_native_location"]
        found.update(range(low, high + 1))
    return sorted(found), []


def dappscan(ledger: Ledger) -> None:
    root = ledger.config.datasets["dappscan"].path
    groups, meta = load_project_groups(root, ledger.config.project_directory_aliases)
    artifacts: dict[str, Artifact] = {}
    for path in tqdm(
        sorted((root / "DAppSCAN-source/contracts").rglob("*.sol")),
        desc="DAppSCAN sources",
        mininterval=5,
    ):
        directory = path.relative_to(root / "DAppSCAN-source/contracts").parts[0]
        references = meta["directory_metadata"][directory]["repository_keys"]
        artifact = ledger.file("dappscan", path, project_keys=[groups[directory], *references])
        artifact.ancestry_known = bool(references)
        artifacts[path.relative_to(root).as_posix()] = artifact
    for path in sorted((root / "DAppSCAN-source/SWCsource").rglob("*.json")):
        document = FileAnnotations.model_validate_json(path.read_text(encoding="utf-8"))
        contained_path(root, document.filePath)
        if document.filePath not in artifacts:
            raise ValueError(f"Missing DAppSCAN annotation target: {document.filePath}")
        for i, ann in enumerate(document.SWCs):
            match = re.match(r"SWC-(\d{3})(?:-|$)", ann.category)
            if not match:
                raise ValueError(f"Unknown DAppSCAN property: {ann.category}")
            lines, flags = parse_lines(ann.lineNumber)
            scope = ann.function.strip()
            is_file = scope.lower() in {"", "n/a", "na", "none", "all", "all functions"}
            ledger.assess(
                artifacts[document.filePath],
                annotation=path,
                native_id=str(i),
                prop=ann.category,
                verdict="PRESENT",
                checks=ledger.mapping("swc_candidates", match[1]),
                kind="FILE" if is_file else "FUNCTION",
                scope="FILE" if is_file else scope,
                lines=lines,
                issues=flags,
                metadata={"native_location": ann.lineNumber},
                reference="https://github.com/InPlusLab/DAppSCAN",
            )


def smartbugs(ledger: Ledger) -> None:
    root = ledger.config.datasets["smartbugs"].path
    artifacts = {
        p.relative_to(root).as_posix(): ledger.file("smartbugs", p)
        for p in sorted((root / "dataset").rglob("*.sol"))
    }
    annotation = root / "vulnerabilities.json"
    seen: set[str] = set()
    for row in json.loads(annotation.read_text(encoding="utf-8")):
        entry = SmartBugsEntry.model_validate(row)
        if entry.path in seen:
            raise ValueError(f"Duplicate SmartBugs entry: {entry.path}")
        seen.add(entry.path)
        contained_path(root, entry.path)
        if entry.path not in artifacts:
            raise ValueError(f"Missing SmartBugs source: {entry.path}")
        for i, vulnerability in enumerate(entry.vulnerabilities):
            ledger.assess(
                artifacts[entry.path],
                annotation=annotation,
                native_id=f"{entry.path}:{i}",
                prop=vulnerability.category,
                verdict="PRESENT",
                checks=ledger.mapping("category_candidates", vulnerability.category),
                lines=vulnerability.lines,
                reference=entry.source or "https://github.com/smartbugs/smartbugs-curated",
            )


def salzano(ledger: Ledger) -> None:
    root = ledger.config.datasets["salzano"].path
    path = root / "csvs/sample_of_interest_with_code.csv"
    csv.field_size_limit(100_000_000)
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["label", "tag", "contract", "contract_code"]:
            raise ValueError("Unexpected Salzano CSV schema")
        for i, row in enumerate(reader):
            role = "smartbugs_external" if row["label"] == "smartbugs_curated" else "development"
            art = ledger.artifact(
                "salzano",
                f"csvs/sample_of_interest_with_code.csv#row={i + 2}",
                row["contract_code"].encode(),
                collection=row["label"],
                project_keys=deployment_key(row["contract"]),
                role=role,
            )
            tags = row["tag"].strip().strip(";").strip()
            if tags == "no":
                ledger.assess(
                    art,
                    annotation=path,
                    native_id=str(i + 2),
                    prop="no_findings",
                    verdict="ABSENT",
                    checks=["REENTRANCY"],
                    issues=["negative_coverage_review_required"],
                    reference="https://arxiv.org/abs/2505.15756",
                )
                continue
            by_category: dict[str, list[int]] = defaultdict(list)
            for tag in tags.split(";"):
                match = re.fullmatch(r"\s*(\d+)\s*:\s*([a-zA-Z_ ]+)\s*", tag)
                if not match:
                    raise ValueError(f"Unparsed Salzano annotation at row {i + 2}: {tag}")
                by_category[match[2].strip()].append(int(match[1]))
            for category, lines in sorted(by_category.items()):
                ledger.assess(
                    art,
                    annotation=path,
                    native_id=str(i + 2),
                    prop=category,
                    verdict="PRESENT",
                    checks=ledger.mapping("category_candidates", category),
                    lines=lines,
                    reference="https://arxiv.org/abs/2505.15756",
                )
    # Raw aliases are indexed even when the published CSV supplies the assessment context.
    for source in sorted((root / "contracts").rglob("*.sol")):
        ledger.file(
            "salzano",
            source,
            collection=source.parent.name,
            role="smartbugs_external" if "smartbugs_curated" in source.parts else "development",
        )
