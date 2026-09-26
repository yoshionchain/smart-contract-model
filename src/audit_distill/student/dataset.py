"""Build the student datasets: one shared train cohort, three target formats, eval inputs.

Label-SFT, Report-SFT (analysis first) and Report-SFT-VF (verdict first) train on the
same accepted train IDs in the same order; only the system prompt's stated format and
the assistant target differ. A train query stays only if the teacher's label-blind
report agreed with the label and its matched partner stayed too, and every condition's
full chat sequence fits the limit. Validation and test keep every query (verdict-based
checkpoint selection and evaluation need no teacher report). Nothing is truncated.
"""

import json
import logging
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Literal

import pyarrow.parquet as pq
import yaml
from pydantic import Field

from audit_distill.config import ConfigModel, TokenizerConfig
from audit_distill.data.release import verify_release
from audit_distill.payload import render_query
from audit_distill.provenance import digest, file_sha256, project_provenance, write_json
from audit_distill.scoped_reports import ORDERS, ScopedReport, canonical_json
from audit_distill.teacher.generate import (
    TeacherConfig,
    is_terminal,
    load_teacher_config,
    read_jsonl,
    run_settings,
)

logger = logging.getLogger(__name__)
Condition = Literal["label", "report", "report_vf"]
CONDITIONS: tuple[Condition, ...] = ("label", "report", "report_vf")
ORDER = {"report": "analysis_first", "report_vf": "verdict_first"}
EVAL_SPLITS = ("validation", "test")
Messages = list[dict[str, str]]


class StudentConfig(ConfigModel):
    version: Literal["3.0"]
    release_dir: Path
    teacher_dir: Path
    output_dir: Path
    manifest_dir: Path
    prompts: dict[Condition, Path]
    max_new_tokens: dict[Condition, int]
    min_train_groups_per_polarity: int = Field(ge=1)
    seed: int


def load_student_config(
    path: Path, root: Path
) -> tuple[StudentConfig, TeacherConfig, TokenizerConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("release_dir", "teacher_dir", "output_dir", "manifest_dir"):
        data[key] = root / data[key]
    data["prompts"] = {k: root / v for k, v in data["prompts"].items()}
    teacher, tokenizer = load_teacher_config(root / "configs/teacher.yaml", root)
    return StudentConfig.model_validate(data), teacher, tokenizer


def accepted_reports(teacher: TeacherConfig, tokenizer: TokenizerConfig) -> dict[str, dict]:
    """Final teacher record per train query, from a complete run with the frozen settings."""
    run_dir = teacher.output_dir / "train"
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if run["settings"] != run_settings(teacher, tokenizer):
        raise ValueError("The train teacher run used other settings than the frozen teacher")
    history: dict[str, list[dict]] = defaultdict(list)
    for record in read_jsonl(run_dir / "items.jsonl"):
        history[str(record["query_id"])].append(record)
    if set(history) != set(run["query_ids"]) or not all(
        is_terminal(h, teacher.max_attempts) for h in history.values()
    ):
        raise ValueError("The train teacher run is incomplete; resume it first")
    return {qid: records[-1] for qid, records in history.items()}


def build_student_data(
    config: StudentConfig, teacher: TeacherConfig, tokenizer_config: TokenizerConfig, root: Path
) -> dict[str, object]:
    from transformers import AutoTokenizer

    manifest = verify_release(config.release_dir)
    if manifest["release_content_sha256"] != teacher.release_content_sha256:
        raise ValueError("Release differs from the release the teacher was pinned to")
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_config.model_id, revision=tokenizer_config.revision, trust_remote_code=False
    )

    def tokens(messages: Messages, *, generation: bool = False) -> int:
        ids = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=generation
        )
        return len(ids)

    systems = {c: config.prompts[c].read_text(encoding="utf-8").strip() for c in CONDITIONS}
    splits = {
        name: sorted(
            pq.read_table(config.release_dir / f"{name}.parquet").to_pylist(),
            key=lambda r: r["query_id"],
        )
        for name in ("train", *EVAL_SPLITS)
    }

    def prompt(condition: Condition, row: dict) -> Messages:
        user = render_query(
            row["check_id"],
            row["definition"],
            row["scope_kind"],
            row["scope_name"],
            row["assumptions"],
            row["source"],
        )
        return [
            {"role": "system", "content": systems[condition]},
            {"role": "user", "content": user},
        ]

    # Train: teacher acceptance, pairwise removal, sequence limit for every condition.
    final = accepted_reports(teacher, tokenizer_config)
    train = {r["query_id"]: r for r in splits["train"]}
    records: dict[Condition, dict[str, dict]] = {c: {} for c in CONDITIONS}
    exclusions: list[dict[str, str]] = []
    too_long: set[str] = set()
    for qid, row in train.items():
        if final[qid]["status"] != "accepted":
            continue
        report = ScopedReport.model_validate(final[qid]["report"])
        if report.verdict != row["label"]:
            raise ValueError(f"Accepted report disagrees with its label: {qid}")
        targets = {
            "label": row["label"],
            "report": canonical_json(report, ORDER["report"]),
            "report_vf": canonical_json(report, ORDER["report_vf"]),
        }
        for condition in CONDITIONS:
            messages = prompt(condition, row)
            completion = [{"role": "assistant", "content": targets[condition]}]
            prompt_tokens = tokens(messages, generation=True)
            sequence_tokens = tokens(messages + completion)
            if sequence_tokens > tokenizer_config.max_sequence_tokens:
                too_long.add(qid)
            records[condition][qid] = {
                "id": qid,
                "label": row["label"],
                "collection": row["collection"],
                "group_id": row["group_id"],
                "prompt": messages,
                "completion": completion,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": sequence_tokens - prompt_tokens,
                "sequence_tokens": sequence_tokens,
            }
    kept: list[str] = []
    for row in train.values():
        if row["match_role"] != "case":
            continue
        pair = (row["query_id"], row["match_partner"])
        reasons = []
        for qid in pair:
            status = final[qid]["status"]
            if status != "accepted":
                reasons.append(f"teacher_{status}")
            elif qid in too_long:
                reasons.append("overlength_sequence")
            else:
                reasons.append("")
        if not any(reasons):
            kept += pair
            continue
        for qid, reason in zip(pair, reasons, strict=True):
            exclusions.append(
                {
                    "query_id": qid,
                    "label": train[qid]["label"],
                    "collection": train[qid]["collection"],
                    "reason": reason or "partner_removed",
                }
            )
    # One seeded order shared by all conditions.
    kept.sort(key=lambda qid: digest([config.seed, qid]))
    groups = {
        v: len({train[q]["group_id"] for q in kept if train[q]["label"] == v})
        for v in ("PRESENT", "ABSENT")
    }
    if min(groups.values()) < config.min_train_groups_per_polarity:
        raise ValueError(f"Train group gate failed after teacher filtering: {groups}")

    # Evaluation inputs: every query, one prompt per evaluation format.
    evaluation: dict[str, dict[Condition, list[dict]]] = {}
    for split in EVAL_SPLITS:
        evaluation[split] = {}
        for condition in CONDITIONS:
            rows = []
            for row in splits[split]:
                messages = prompt(condition, row)
                prompt_tokens = tokens(messages, generation=True)
                budget = prompt_tokens + config.max_new_tokens[condition]
                if budget > tokenizer_config.max_sequence_tokens:
                    raise ValueError(f"{split} query {row['query_id']} exceeds the sequence limit")
                rows.append(
                    {
                        "id": row["query_id"],
                        "label": row["label"],
                        "collection": row["collection"],
                        "group_id": row["group_id"],
                        "pragma_minor": row["pragma_minor"],
                        "line_count": len(row["source"].splitlines()),
                        "prompt": messages,
                        "prompt_tokens": prompt_tokens,
                    }
                )
            evaluation[split][condition] = rows

    statistics = student_statistics(train, kept, exclusions, records, groups)
    template_sha = digest(tokenizer.chat_template)
    output = config.output_dir
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".student-", dir=output.parent) as temporary:
        stage = Path(temporary)
        for condition in CONDITIONS:
            write_jsonl(stage / f"train_{condition}.jsonl", [records[condition][q] for q in kept])
            for split in EVAL_SPLITS:
                write_jsonl(stage / f"{split}_{condition}.jsonl", evaluation[split][condition])
        write_json(
            stage / "shared_cohort.json",
            {
                "train_ids": kept,
                "validation_ids": [r["query_id"] for r in splits["validation"]],
                "test_ids": [r["query_id"] for r in splits["test"]],
                "train_exclusions": sorted(exclusions, key=lambda e: e["query_id"]),
            },
        )
        write_json(stage / "student_statistics.json", statistics)
        write_json(stage / "provenance.json", {"project": project_provenance(root)})
        files = {p.name: file_sha256(p) for p in sorted(stage.iterdir())}
        data_files = {k: v for k, v in files.items() if k != "provenance.json"}
        student_manifest = {
            "version": config.version,
            "student_content_sha256": digest(data_files),
            "files": files,
            "release_content_sha256": manifest["release_content_sha256"],
            "teacher_settings_key": run_settings(teacher, tokenizer_config)["settings_key"],
            "tokenizer": f"{tokenizer_config.model_id}@{tokenizer_config.revision}",
            "chat_template_sha256": template_sha,
            "prompt_sha256": {c: file_sha256(config.prompts[c]) for c in CONDITIONS},
            "field_orders": {c: list(ORDERS[o]) for c, o in ORDER.items()},
            "counts": {"train": len(kept)} | {s: len(splits[s]) for s in EVAL_SPLITS},
        }
        write_json(stage / "student_manifest.json", student_manifest)
        output.mkdir(exist_ok=True)
        for old in output.iterdir():
            old.unlink()
        for path in sorted(stage.iterdir()):
            os.replace(path, output / path.name)
    config.manifest_dir.mkdir(parents=True, exist_ok=True)
    for name in ("student_manifest.json", "student_statistics.json"):
        (config.manifest_dir / name).write_bytes((output / name).read_bytes())
    return student_manifest


def student_statistics(
    train: dict[str, dict],
    kept: list[str],
    exclusions: list[dict[str, str]],
    records: dict[Condition, dict[str, dict]],
    groups: dict[str, int],
) -> dict[str, object]:
    """Cohort size, acceptance bias (kept vs all train) and per-condition token exposure."""

    def cells(ids: list[str]) -> dict[str, dict[str, int]]:
        counter: dict[str, Counter[str]] = defaultdict(Counter)
        for qid in ids:
            counter[train[qid]["collection"]][train[qid]["label"]] += 1
        return {c: dict(sorted(v.items())) for c, v in sorted(counter.items())}

    def source_tokens(ids: list[str]) -> float:
        return round(mean(train[q]["source_tokens"] for q in ids), 1)

    everything = sorted(train)
    exposure: dict[str, dict[str, float]] = {}
    for condition, rows in records.items():
        completion = [rows[q]["completion_tokens"] for q in kept]
        sequence = [rows[q]["sequence_tokens"] for q in kept]
        exposure[condition] = {
            "completion_tokens_total": sum(completion),
            "completion_tokens_median": median(completion),
            "sequence_tokens_max": max(sequence),
        }
    pragma = {
        name: dict(sorted(Counter(train[q]["pragma_minor"] for q in ids).items()))
        for name, ids in (("all_train", everything), ("kept", kept))
    }
    return {
        "train_kept": len(kept),
        "train_pairs": len(kept) // 2,
        "train_groups_per_label": groups,
        "exclusion_reasons": dict(sorted(Counter(e["reason"] for e in exclusions).items())),
        "acceptance_bias": {
            "all_train": cells(everything),
            "kept": cells(kept),
            "pragma": pragma,
            "mean_source_tokens": {
                "all_train": source_tokens(everything),
                "kept": source_tokens(kept),
            },
        },
        "token_exposure": exposure,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )
