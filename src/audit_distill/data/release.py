"""Build the v3.0 dataset: read the pinned benchmark, exclude, group, split and balance.

Labels are the benchmark's expert labels (reentrant/safe folders, RSD file suffixes),
used as-is under its operational definition. Every contract is one whole-file query.
Comments are blanked without moving lines; overlength sources are excluded, never
truncated; no group crosses partitions; each partition is balanced 1:1 per collection.
"""

import json
import logging
import os
import re
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict
from sklearn.model_selection import StratifiedGroupKFold
from tqdm import tqdm

from audit_distill.data.comments import strip_comments
from audit_distill.data.fetch import verify_checkout
from audit_distill.data.groups import group_contracts
from audit_distill.data.identity import code_identity
from audit_distill.data.line_numbers import render_line_numbers
from audit_distill.data.settings import DataConfig
from audit_distill.provenance import digest, file_sha256, project_provenance, write_json

logger = logging.getLogger(__name__)

Polarity = Literal["PRESENT", "ABSENT"]
Partition = Literal["train", "validation", "test"]
Collection = Literal["aggregated", "rsd"]
PARTITIONS: tuple[Partition, ...] = ("train", "validation", "test")
POLARITIES: tuple[Polarity, ...] = ("PRESENT", "ABSENT")
AGGREGATED = {
    "PRESENT": "aggregated-benchmark/src/reentrant",
    "ABSENT": "aggregated-benchmark/src/safe",
}
RSD_NAME = re.compile(r"^(?P<family>.+)_(?P<kind>ree|safe)\d+\.sol$")
ORIGIN = re.compile(r"_(cgt|hg|rs)\.sol$")
PRAGMA = re.compile(r"pragma\s+solidity\s*[^;\d]*(\d+)\.(\d+)")


class Row(BaseModel):
    """One release query: a whole contract, its expert label and its exact model input."""

    model_config = ConfigDict(extra="forbid")
    version: Literal["3.0"] = "3.0"
    query_id: str
    path: str  # upstream path, provenance only; never part of a model input
    collection: Collection
    origin: str
    group_id: str = ""
    code_identity_sha256: str
    model_input_sha256: str
    label: Polarity
    pragma_minor: str
    source_tokens: int
    match_role: Literal["case", "control"] | None = None
    match_partner: str | None = None
    match_level: int | None = None
    partition: Partition | None = None
    check_id: str
    definition: str
    scope_kind: Literal["FILE"] = "FILE"
    scope_name: Literal["FILE"] = "FILE"
    assumptions: list[str]
    source: str


def model_input(check_id: str, definition: str, assumptions: list[str], source: str) -> dict:
    """The exact payload shared by teacher, student and every evaluation mode."""
    return {
        "check_id": check_id,
        "definition": definition,
        "scope": {"kind": "FILE", "name": "FILE"},
        "assumptions": assumptions,
        "source": source,
    }


def benchmark_files(root: Path) -> list[tuple[Path, Collection, Polarity, str]]:
    """(path, collection, label, origin or RSD family) for every benchmark contract."""
    files: list[tuple[Path, Collection, Polarity, str]] = []
    for label, folder in AGGREGATED.items():
        for path in sorted((root / "benchmarks" / folder).glob("*.sol")):
            match = ORIGIN.search(path.name)
            files.append((path, "aggregated", label, match[1] if match else "rs_pool"))
    for path in sorted((root / "benchmarks/RSD/src").glob("*.sol")):
        match = RSD_NAME.match(path.name)
        if match is None:
            raise ValueError(f"Unexpected RSD file name: {path.name}")
        label: Polarity = "PRESENT" if match["kind"] == "ree" else "ABSENT"
        files.append((path, "rsd", label, match["family"]))
    return files


def read_benchmark(
    config: DataConfig, count_tokens: Callable[[str], int]
) -> tuple[list[Row], dict[str, str], list[dict[str, str]]]:
    """Rows, RSD families by query and exclusions (never relabelled)."""
    root = config.source.path
    rows: list[Row] = []
    families: dict[str, str] = {}
    exclusions: list[dict[str, str]] = []
    leak = re.compile(re.escape(config.label_leak_pattern))
    for path, collection, label, origin in tqdm(benchmark_files(root), desc="Contracts"):
        relative = str(path.relative_to(root))
        where = {"path": relative, "collection": collection, "label": label}
        if collection == "aggregated" and origin in config.excluded_origins:
            exclusions.append(where | {"reason": "bug_injection_tool"})
            continue
        try:
            code = strip_comments(path.read_text(encoding="utf-8"))
            identity = code_identity(code)
        except (UnicodeDecodeError, ValueError):
            exclusions.append(where | {"reason": "unreadable_source"})
            continue
        if leak.search(code):
            exclusions.append(where | {"reason": "label_leaking_identifiers"})
            continue
        source = render_line_numbers(code)
        tokens = count_tokens(source)
        if tokens > config.tokenizer.max_code_tokens:
            exclusions.append(where | {"reason": "overlength_source"})
            continue
        payload = model_input(config.check_id, config.definition, config.assumptions, source)
        pragma = PRAGMA.search(code)
        row = Row(
            query_id=digest(payload),
            path=relative,
            collection=collection,
            origin=origin if collection == "aggregated" else "rsd",
            code_identity_sha256=identity,
            model_input_sha256=digest(payload),
            label=label,
            pragma_minor=f"{pragma[1]}.{pragma[2]}" if pragma else "unspecified",
            source_tokens=tokens,
            check_id=config.check_id,
            definition=config.definition,
            assumptions=config.assumptions,
            source=source,
        )
        rows.append(row)
        if collection == "rsd":
            families[row.query_id] = origin
    # Identical code once: conflicting labels exclude every copy, agreeing ones keep one.
    by_identity: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        by_identity[row.code_identity_sha256].append(row)
    kept: list[Row] = []
    for copies in by_identity.values():
        copies.sort(key=lambda r: r.path)
        if len({r.label for r in copies}) > 1:
            reason, keep = "conflicting_duplicate", []
        else:
            reason, keep = "duplicate", copies[:1]
        kept += keep
        for row in copies[len(keep) :]:
            exclusions.append(
                {
                    "path": row.path,
                    "collection": row.collection,
                    "label": row.label,
                    "reason": reason,
                }
            )
    return sorted(kept, key=lambda r: r.query_id), families, exclusions


def balance(rows: list[Row], levels: list[list[str]], seed: int) -> tuple[list[Row], list[Row]]:
    """1:1 matching per (partition, collection): every minority-label query gets one control.

    Levels are tried in order across all cases; within a level, controls from less-used
    groups come first, then a seeded hash order. Unmatched controls are surplus.
    """
    selected: list[Row] = []
    surplus: list[Row] = []
    cells: dict[tuple[str, str], list[Row]] = defaultdict(list)
    for row in rows:
        cells[(str(row.partition), row.collection)].append(row)
    for key in sorted(cells):
        by_label = {
            v: sorted(
                (r for r in cells[key] if r.label == v), key=lambda r: digest([seed, r.query_id])
            )
            for v in POLARITIES
        }
        minority = min(POLARITIES, key=lambda v: (len(by_label[v]), v))
        cases = by_label[minority]
        controls = by_label["ABSENT" if minority == "PRESENT" else "PRESENT"]
        used: set[str] = set()
        group_use: Counter[str] = Counter()
        matched: dict[str, tuple[Row, int]] = {}
        for level, fields in enumerate(levels):
            for case in cases:
                if case.query_id in matched:
                    continue
                pool = [
                    c
                    for c in controls
                    if c.query_id not in used
                    and all(getattr(c, f) == getattr(case, f) for f in fields)
                ]
                if pool:
                    control = min(
                        pool, key=lambda c: (group_use[c.group_id], digest([seed, c.query_id]))
                    )
                    used.add(control.query_id)
                    group_use[control.group_id] += 1
                    matched[case.query_id] = (control, level)
        for case in cases:
            control, level = matched[case.query_id]
            selected += [
                case.model_copy(
                    update={
                        "match_role": "case",
                        "match_partner": control.query_id,
                        "match_level": level,
                    }
                ),
                control.model_copy(
                    update={
                        "match_role": "control",
                        "match_partner": case.query_id,
                        "match_level": level,
                    }
                ),
            ]
        surplus += [c for c in controls if c.query_id not in used]
    return sorted(selected, key=lambda r: r.query_id), surplus


def partition_summary(rows: list[Row]) -> dict[str, object]:
    cells: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(POLARITIES, 0))
    for row in rows:
        cells[row.collection][row.label] += 1
    return {
        "queries": {c: dict(v) for c, v in sorted(cells.items())},
        "groups": {v: len({r.group_id for r in rows if r.label == v}) for v in POLARITIES},
    }


def grouped_split(
    rows: list[Row], config: DataConfig
) -> tuple[list[Row], list[Row], int, list[dict[str, object]]]:
    """StratifiedGroupKFold over groups (strata = collection x label), then balance.

    The first seed whose balanced partitions pass the group gates and contain both
    labels of every collection is used; seeds are never chosen from model results.
    """
    strata = [f"{r.collection}|{r.label}" for r in rows]
    groups = [r.group_id for r in rows]
    gates = config.min_groups_per_polarity.model_dump()
    attempts: list[dict[str, object]] = []
    for seed in range(config.split_seed_first, config.split_seed_last + 1):
        folds = StratifiedGroupKFold(n_splits=config.folds, shuffle=True, random_state=seed)
        assignment: dict[str, Partition] = {}
        for fold, (_, members) in enumerate(folds.split(rows, strata, groups)):
            name: Partition = (
                "test"
                if fold in config.test_folds
                else "validation"
                if fold in config.validation_folds
                else "train"
            )
            for index in members:
                assignment[rows[index].group_id] = name
        assigned = [r.model_copy(update={"partition": assignment[r.group_id]}) for r in rows]
        selected, surplus = balance(assigned, config.match_levels, config.seed)
        summary = {
            name: partition_summary([r for r in selected if r.partition == name])
            for name in PARTITIONS
        }
        passed = all(
            summary[name]["groups"][v] >= gates[name]
            and len(summary[name]["queries"]) == 2
            and all(n > 0 for cell in summary[name]["queries"].values() for n in cell.values())
            for name in PARTITIONS
            for v in POLARITIES
        )
        attempts.append({"seed": seed, "passed": passed, "partitions": summary})
        if passed:
            return selected, surplus, seed, attempts
    raise ValueError("No split seed satisfies the group and breadth gates")


def write_rows(path: Path, rows: list[Row]) -> None:
    pq.write_table(pa.Table.from_pylist([r.model_dump() for r in rows]), path)


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def load_counter(config: DataConfig) -> Callable[[str], int]:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        config.tokenizer.model_id, revision=config.tokenizer.revision, trust_remote_code=False
    )
    return lambda text: len(
        tokenizer.encode(text, add_special_tokens=False, truncation=False, verbose=False)
    )


def build_release(config: DataConfig, root: Path) -> dict[str, object]:
    upstream = verify_checkout(config.source)
    rows, families, exclusions = read_benchmark(config, load_counter(config))
    group_of, edges = group_contracts(
        {r.query_id: strip_source(r.source) for r in rows},
        families,
        min_tokens=config.near_clone_min_tokens,
        jaccard=config.near_clone_jaccard,
        length_ratio=config.near_clone_length_ratio,
    )
    rows = [r.model_copy(update={"group_id": group_of[r.query_id]}) for r in rows]
    logger.info("%s usable contracts in %s groups", len(rows), len(set(group_of.values())))
    selected, surplus, seed, attempts = grouped_split(rows, config)
    logger.info("Split seed %s after %s attempt(s)", seed, len(attempts))
    exclusions += [
        {
            "path": r.path,
            "collection": r.collection,
            "label": r.label,
            "reason": "balancing_surplus",
            "partition": str(r.partition),
        }
        for r in surplus
    ]
    reasons: dict[str, Counter[str]] = defaultdict(Counter)
    for e in exclusions:
        reasons[e["reason"]][f"{e['collection']}|{e['label']}"] += 1
    statistics = {
        "version": config.version,
        "source": upstream,
        "usable_before_balancing": partition_summary(rows),
        "groups": len(set(group_of.values())),
        "exclusions": {k: dict(sorted(v.items())) for k, v in sorted(reasons.items())},
        "split_seed": seed,
        "split_attempts": len(attempts),
        "partitions": {
            name: partition_summary([r for r in selected if r.partition == name])
            for name in PARTITIONS
        },
        "match_levels": dict(
            sorted(Counter(str(r.match_level) for r in selected if r.match_role == "case").items())
        ),
        "pragma_by_label": {
            v: dict(sorted(Counter(r.pragma_minor for r in selected if r.label == v).items()))
            for v in POLARITIES
        },
    }
    output = config.output_dir
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".release-", dir=output.parent) as temporary:
        stage = Path(temporary)
        for name in PARTITIONS:
            write_rows(stage / f"{name}.parquet", [r for r in selected if r.partition == name])
        write_jsonl(
            stage / "exclusions.jsonl", sorted(exclusions, key=lambda e: (e["path"], e["reason"]))
        )
        write_jsonl(stage / "group_edges.jsonl", edges)
        write_json(stage / "split_attempts.json", attempts)
        write_json(stage / "release_statistics.json", statistics)
        write_json(
            stage / "effective_config.json",
            json.loads(config.model_dump_json())
            | {
                "source": {**upstream, "sparse_paths": config.source.sparse_paths},
                "output_dir": str(config.output_dir.relative_to(root)),
                "manifest_dir": str(config.manifest_dir.relative_to(root)),
            },
        )
        write_json(stage / "provenance.json", {"project": project_provenance(root)})
        files = {p.name: file_sha256(p) for p in sorted(stage.iterdir())}
        data_files = {k: v for k, v in files.items() if k != "provenance.json"}
        manifest = {
            "version": config.version,
            "release_content_sha256": digest(data_files),
            "files": files,
            "split_seed": seed,
            "counts": statistics["partitions"],
        }
        write_json(stage / "release_manifest.json", manifest)
        output.mkdir(exist_ok=True)
        for old in output.iterdir():
            old.unlink()
        for path in sorted(stage.iterdir()):
            os.replace(path, output / path.name)
    config.manifest_dir.mkdir(parents=True, exist_ok=True)
    for name in ("release_manifest.json", "release_statistics.json"):
        (config.manifest_dir / name).write_bytes((output / name).read_bytes())
    return manifest


def strip_source(numbered: str) -> str:
    """Code from a numbered source (for grouping), dropping the `0001 | ` prefixes."""
    return "\n".join(line.split("|", 1)[1][1:] for line in numbered.split("\n"))


def verify_release(directory: Path) -> dict[str, object]:
    manifest = json.loads((directory / "release_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != "3.0":
        raise ValueError("Expected a v3.0 release manifest")
    for name, checksum in manifest["files"].items():
        path = directory / name
        if Path(name).name != name or not path.is_file() or file_sha256(path) != checksum:
            raise ValueError(f"Incomplete or modified release artifact: {name}")
    data_files = {k: v for k, v in manifest["files"].items() if k != "provenance.json"}
    if digest(data_files) != manifest["release_content_sha256"]:
        raise ValueError("Release content fingerprint mismatch")
    return manifest
