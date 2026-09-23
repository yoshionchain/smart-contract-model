"""Native scoped judgments. Blank cells and tool output never become ABSENT."""

import csv
import json

from audit_distill.data.ingest import deployment_key
from audit_distill.data.ledger import Ledger
from audit_distill.data.records import Verdict
from audit_distill.provenance import file_sha256


def native_verdict(value: str | None) -> Verdict:
    value = (value or "").strip().lower()
    if value in {"1", "t"}:
        return "PRESENT"
    if value in {"0", "f"}:
        return "ABSENT"
    if value in {"", "n/a"}:
        return "UNKNOWN"
    raise ValueError(f"Unrecognized native verdict: {value!r}")


def scrubd(ledger: Ledger) -> None:
    root = ledger.config.datasets["scrubd"].path
    base = root / "SCRUBD-CD/data"
    sources = {
        p.stem.lower(): ledger.file(
            "scrubd", p, collection="SCRUBD-CD", project_keys=deployment_key(p.stem)
        )
        for p in sorted((base / "solidity_codes").glob("*.sol"))
    }
    annotation = base / "labels.csv"
    with annotation.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != [
            "Smart Contract",
            "Function Name",
            "RE",
            "UX",
            "is_student",
            "Comments",
        ]:
            raise ValueError("Unexpected SCRUBD labels schema")
        for i, row in enumerate(reader):
            key = row["Smart Contract"].strip().lower()
            if key not in sources:
                raise ValueError(f"Missing SCRUBD source: {key}")
            for prop in ["RE", "UX"]:
                verdict = native_verdict(row[prop])
                ledger.assess(
                    sources[key],
                    annotation=annotation,
                    native_id=f"{i + 2}:{prop}",
                    prop=prop,
                    verdict=verdict,
                    kind="FUNCTION",
                    scope=row["Function Name"].strip(),
                    checks=ledger.mapping("native_candidates", f"scrubd:{prop}"),
                    rationale=row["Comments"] or "",
                    metadata={"is_student": row["is_student"]},
                    reference="https://arxiv.org/abs/2412.09935",
                )


def cgt(ledger: Ledger) -> None:
    root = ledger.config.datasets["cgt"].path
    sources = {p.stem: ledger.file("cgt", p) for p in sorted((root / "source").glob("*.sol"))}
    annotation = root / "consolidated.csv"
    annotation_hash = file_sha256(annotation)
    with annotation.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        for i, row in enumerate(reader):
            if not row["fp_sol"]:
                ledger.ingestion_issues.append(
                    {
                        "source": "cgt",
                        "native_id": f"{row['dataset']}:{row['id']}",
                        "reason": "no_published_source",
                        "native_property": row["property"],
                        "native_verdict": row["property_holds"],
                        "annotation_path": "consolidated.csv",
                        "annotation_sha256": annotation_hash,
                        "original_collection": row["dataset"],
                        "native_row_json": json.dumps(row, sort_keys=True),
                    }
                )
                continue
            if row["fp_sol"] not in sources:
                raise ValueError(f"Missing CGT source referenced by metadata: {row['fp_sol']}")
            artifact = sources[row["fp_sol"]]
            if row["chain"] in {"main", "ropsten", "rinkeby"}:
                artifact.project_keys = sorted(
                    set(artifact.project_keys)
                    | set(deployment_key(row["addr"], f"ethereum-{row['chain']}"))
                )
                # A deployment link does not establish independent project ancestry.
            flags = ["native_human_assessment_protocol_unverified"]
            if row["dataset"] not in ledger.config.cgt_original_collections:
                flags.append("excluded_original_collection")
            if row["dataset"] == "SBcurated":
                artifact.role = "smartbugs_external"
            ledger.assess(
                artifact,
                annotation=annotation,
                native_id=f"{row['dataset']}:{row['id']}:{i + 2}",
                prop=row["property"],
                verdict=native_verdict(row["property_holds"]),
                kind="CONTRACT",
                scope=row["contractname"],
                checks=ledger.mapping("swc_candidates", row["swc"]),
                issues=flags,
                metadata={
                    "original_collection": row["dataset"],
                    "native_swc": row["swc"],
                    "deployment": row["addr"],
                    "chain": row["chain"],
                },
                reviewed=False,
                reference="https://arxiv.org/abs/2304.11624",
            )


def scbench(ledger: Ledger) -> None:
    root = ledger.config.datasets["scbench"].path
    base = root / "Empirical Evaluation of Security Analyzers"
    sources = {
        p.name: ledger.file("scbench", p, project_keys=deployment_key(p.stem.split("*")[-1]))
        for p in sorted((base / "Solidity").glob("*.sol"))
    }
    for prop in ["Reentrancy", "Suicide", "IntergerOU"]:
        annotation = base / "Tools_Labels" / f"{prop}_labels.csv"
        with annotation.open(newline="", encoding="utf-8") as stream:
            for i, row in enumerate(csv.DictReader(stream)):
                name = row["contract_address"]
                if name not in sources:
                    raise ValueError(f"Missing ScBench source: {name}")
                ledger.assess(
                    sources[name],
                    annotation=annotation,
                    native_id=str(i + 2),
                    prop=prop,
                    verdict=native_verdict(row["label"]),
                    checks=ledger.mapping("native_candidates", f"scbench:{prop}"),
                    issues=["native_scope_confirmation_required", "execution_assumptions_required"],
                    reference="https://sanadlab.org/assets/pdf/TamerMSR2026.pdf",
                )
