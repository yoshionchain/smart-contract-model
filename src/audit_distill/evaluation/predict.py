"""Greedy predictions for every evaluation mode on one split (GPU; `--smoke` on CPU).

Base modes use the unchanged model; SFT modes load each condition's selected adapter.
Every mode answers the same queries with its own format and generation budget; raw
outputs are kept next to the strictly parsed verdict (INVALID if unparseable).
"""

import json
import logging
from pathlib import Path
from typing import Literal

import yaml

from audit_distill.config import ConfigModel
from audit_distill.inference import Format, generate, read_rows, verdict
from audit_distill.provenance import file_sha256, project_provenance, write_json
from audit_distill.student.dataset import load_student_config
from audit_distill.training.train import environment, load_training_config, verify_student_data

logger = logging.getLogger(__name__)


class Mode(ConfigModel):
    format: Format
    adapter: str | None


class EvaluationConfig(ConfigModel):
    version: Literal["3.0"]
    training_config: Path
    predictions_dir: Path
    results_dir: Path
    teacher_ceiling_dir: Path
    modes: dict[str, Mode]
    comparisons: list[tuple[str, str]]
    bootstrap_seed: int
    bootstrap_replicates: int
    bootstrap_max_draws: int
    tfidf_token_pattern: str
    tfidf_ngram_max: int
    logistic_c: float
    seed: int


def load_evaluation_config(path: Path, root: Path) -> EvaluationConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("training_config", "predictions_dir", "results_dir", "teacher_ceiling_dir"):
        data[key] = root / data[key]
    return EvaluationConfig.model_validate(data)


def predict(config: EvaluationConfig, root: Path, split: str, smoke: bool = False) -> dict:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    training = load_training_config(config.training_config, root)
    student, _, _ = load_student_config(training.student_config, root)
    verify_student_data(student)
    model_id, revision = training.base_model, training.model_revision
    output = config.predictions_dir / split
    if smoke:
        model_id, revision = training.smoke.model_id, training.smoke.model_revision
        output = config.predictions_dir.with_name("eval-smoke") / split
    cuda = torch.cuda.is_available()
    if not smoke and not cuda:
        raise ValueError("Predictions for results need a CUDA GPU (use --smoke on CPU)")
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    base = AutoModelForCausalLM.from_pretrained(
        model_id, revision=revision, dtype=torch.bfloat16 if cuda else torch.float32
    )
    base.eval()
    if cuda:
        base.to("cuda")
    output.mkdir(parents=True, exist_ok=True)
    peft: PeftModel | None = None
    summary: dict[str, dict] = {}
    # Base modes first, on the untouched model; then one adapter at a time.
    ordered = sorted(config.modes.items(), key=lambda item: item[1].adapter is not None)
    for name, mode in ordered:
        rows = read_rows(student.output_dir / f"{split}_{mode.format}.jsonl")
        budget = student.max_new_tokens[mode.format]
        if smoke:
            rows, budget = rows[: training.smoke.validation_examples], training.smoke.max_new_tokens
        model = base
        adapter_info = None
        if mode.adapter is not None:
            run_dir = training.output_dir / (f"smoke-{mode.format}" if smoke else mode.adapter)
            adapter = run_dir / "adapter"
            if peft is None:
                peft = PeftModel.from_pretrained(base, str(adapter), adapter_name=name)
            else:
                peft.load_adapter(str(adapter), adapter_name=name)
            peft.set_adapter(name)
            peft.eval()
            model = peft
            selection = json.loads((run_dir / "selection.json").read_text(encoding="utf-8"))
            adapter_info = {
                "run": str(run_dir.relative_to(root)),
                "best_epoch": selection["best_epoch"],
                "adapter_sha256": file_sha256(adapter / "adapter_model.safetensors"),
            }
        if model is base and peft is not None:
            raise ValueError("Base modes must run before any adapter is attached")
        logger.info("Predicting %s (%s, %s queries)", name, mode.format, len(rows))
        raw = generate(model, tokenizer, rows, budget, training.generation_batch_size)
        with (output / f"{name}.jsonl").open("w", encoding="utf-8") as stream:
            for row, text in zip(rows, raw, strict=True):
                predicted = verdict(mode.format, text, row["line_count"])
                record = {
                    "id": row["id"],
                    "gold": row["label"],
                    "predicted": predicted,
                    "raw": text,
                    "collection": row["collection"],
                    "group_id": row["group_id"],
                    "pragma_minor": row["pragma_minor"],
                    "line_count": row["line_count"],
                }
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        summary[name] = {"format": mode.format, "adapter": adapter_info, "queries": len(rows)}
    manifest = {
        "split": split,
        "smoke": smoke,
        "model": {"id": model_id, "revision": revision},
        "modes": summary,
        "files": {p.name: file_sha256(p) for p in sorted(output.glob("*.jsonl"))},
        "environment": environment(),
        "provenance": project_provenance(root),
    }
    write_json(output / "predictions_manifest.json", manifest)
    return manifest
