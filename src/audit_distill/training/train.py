"""LoRA fine-tuning (BF16 base) of one student condition, then per-epoch checkpoint selection.

All conditions train on the same shared cohort with identical settings; only the chat
records differ. Loss covers assistant tokens only (prompt/completion records). After
training, every epoch's adapter greedily decodes all validation queries in the
condition's own format (Multi-SFT: label format); the best validation macro-F1 wins
(ties: earlier epoch).
"""

import json
import logging
import platform
import shutil
import subprocess
import time
from importlib.metadata import version
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from audit_distill.config import ConfigModel
from audit_distill.inference import Format, generate, macro_f1, read_rows, verdict
from audit_distill.provenance import digest, file_sha256, project_provenance, write_json
from audit_distill.student.dataset import StudentConfig, load_student_config

logger = logging.getLogger(__name__)


class SmokeConfig(ConfigModel):
    model_id: str
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    train_examples: int = Field(ge=1)
    validation_examples: int = Field(ge=1)
    max_new_tokens: int = Field(ge=1)


class TrainingConfig(ConfigModel):
    version: Literal["3.0"]
    base_model: Literal["Qwen/Qwen3-4B-Instruct-2507"]
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    student_config: Path
    output_dir: Path
    max_seq_length: int
    lora_r: int
    lora_alpha: int
    lora_dropout: float
    lora_bias: Literal["none"]
    lora_targets: list[str]
    learning_rate: float
    num_train_epochs: int
    per_device_train_batch_size: int
    gradient_accumulation_steps: int
    weight_decay: float
    warmup_ratio: float
    lr_scheduler_type: str
    max_grad_norm: float
    gradient_checkpointing: bool
    packing: Literal[False]
    optim: str
    seed: int
    logging_steps: int
    generation_batch_size: int
    smoke: SmokeConfig


def load_training_config(path: Path, root: Path) -> TrainingConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("student_config", "output_dir"):
        data[key] = root / data[key]
    return TrainingConfig.model_validate(data)


def verify_student_data(student: StudentConfig) -> dict:
    """The student files must match their manifest (content hashes)."""
    directory = student.output_dir
    manifest = json.loads((directory / "student_manifest.json").read_text(encoding="utf-8"))
    for name, checksum in manifest["files"].items():
        if file_sha256(directory / name) != checksum:
            raise ValueError(f"Student data file changed since it was built: {name}")
    return manifest


def environment() -> dict[str, object]:
    import torch

    info: dict[str, object] = {
        "python": platform.python_version(),
        "packages": {p: version(p) for p in ("torch", "transformers", "trl", "peft", "accelerate")},
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    if shutil.which("nvidia-smi"):
        info["driver"] = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
        ).stdout.strip()
    return info


Condition = Literal["label", "report", "report_vf", "multi"]


def run_name(condition: str, seed: int, default_seed: int) -> str:
    """Run directory name: `report-vf`, or `report-vf-seed43` for an extra seed."""
    name = condition.replace("_", "-")
    return name if seed == default_seed else f"{name}-seed{seed}"


def train(
    condition: Condition,
    config: TrainingConfig,
    root: Path,
    smoke: bool = False,
    seed: int | None = None,
) -> dict:
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    student, _, _ = load_student_config(config.student_config, root)
    student_manifest = verify_student_data(student)
    # Multi-SFT trains on label and report records and is selected in label mode.
    fmt: Format = "label" if condition == "multi" else condition
    rows = read_rows(student.output_dir / f"train_{condition}.jsonl")
    validation = read_rows(student.output_dir / f"validation_{fmt}.jsonl")
    cohort = json.loads((student.output_dir / "shared_cohort.json").read_text(encoding="utf-8"))
    if list(dict.fromkeys(r["id"] for r in rows)) != cohort["train_ids"]:
        raise ValueError("Train records differ from the shared cohort")
    model_id, revision = config.base_model, config.model_revision
    max_new_tokens = student.max_new_tokens[fmt]
    default_seed = config.seed
    if seed is not None:
        config = config.model_copy(update={"seed": seed})
    name = run_name(condition, config.seed, default_seed)
    run_dir = config.output_dir / (f"smoke-{name.replace('-', '_')}" if smoke else name)
    if smoke:
        model_id, revision = config.smoke.model_id, config.smoke.model_revision
        rows = rows[: config.smoke.train_examples]
        validation = validation[: config.smoke.validation_examples]
        max_new_tokens = config.smoke.max_new_tokens
        shutil.rmtree(run_dir, ignore_errors=True)
    elif (run_dir / "selection.json").exists():
        raise ValueError(f"{run_dir} already holds a finished run")
    run_dir.mkdir(parents=True, exist_ok=True)

    cuda = torch.cuda.is_available()
    if not smoke and not (cuda and torch.cuda.is_bf16_supported()):
        raise ValueError("Real training needs a BF16-capable CUDA GPU (use --smoke on CPU)")
    dtype = torch.bfloat16 if cuda else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, dtype=dtype)
    args = SFTConfig(
        output_dir=str(run_dir / "checkpoints"),
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        warmup_ratio=config.warmup_ratio,
        lr_scheduler_type=config.lr_scheduler_type,
        max_grad_norm=config.max_grad_norm,
        gradient_checkpointing=config.gradient_checkpointing,
        bf16=dtype == torch.bfloat16,
        optim=config.optim if cuda else "adamw_torch",
        seed=config.seed,
        data_seed=config.seed,
        max_length=config.max_seq_length,
        packing=config.packing,
        completion_only_loss=True,
        save_strategy="epoch",
        save_only_model=True,
        logging_steps=config.logging_steps,
        report_to="none",
    )
    peft_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        bias=config.lora_bias,
        target_modules=config.lora_targets,
        task_type="CAUSAL_LM",
    )
    dataset = Dataset.from_list(
        [{"prompt": r["prompt"], "completion": r["completion"]} for r in rows]
    )
    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    lengths = [len(ids) for ids in trainer.train_dataset["input_ids"]]
    if max(lengths) > config.max_seq_length:
        raise ValueError("A training sequence exceeds the limit; nothing may be truncated")
    started = time.monotonic()
    result = trainer.train()
    train_seconds = time.monotonic() - started

    # Checkpoint selection: every epoch's adapter on all validation queries.
    peft_model = trainer.model
    peft_model.gradient_checkpointing_disable()
    peft_model.config.use_cache = True
    peft_model.eval()
    checkpoints = sorted(
        (run_dir / "checkpoints").glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[1])
    )
    gold = [r["label"] for r in validation]
    epochs = []
    for epoch, checkpoint in enumerate(checkpoints, 1):
        name = f"epoch{epoch}"
        peft_model.load_adapter(str(checkpoint), adapter_name=name)
        peft_model.set_adapter(name)
        raw = generate(
            peft_model, tokenizer, validation, max_new_tokens, config.generation_batch_size
        )
        predicted = [
            verdict(fmt, text, r["line_count"]) for text, r in zip(raw, validation, strict=True)
        ]
        score = macro_f1(gold, predicted)
        epochs.append(
            {
                "epoch": epoch,
                "checkpoint": checkpoint.name,
                "validation_macro_f1": score,
                "invalid": predicted.count("INVALID"),
            }
        )
        with (run_dir / f"validation_{name}.jsonl").open("w", encoding="utf-8") as stream:
            for row, text, label in zip(validation, raw, predicted, strict=True):
                record = {"id": row["id"], "gold": row["label"], "predicted": label, "raw": text}
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("%s: validation macro-F1 %.3f (%s invalid)", name, score, epochs[-1]["invalid"])
    best = max(epochs, key=lambda e: (e["validation_macro_f1"], -e["epoch"]))
    adapter_dir = run_dir / "adapter"
    shutil.rmtree(adapter_dir, ignore_errors=True)
    shutil.copytree(run_dir / "checkpoints" / best["checkpoint"], adapter_dir)

    selection = {
        "condition": condition,
        "selection_format": fmt,
        "epochs": epochs,
        "best_epoch": best["epoch"],
    }
    write_json(run_dir / "selection.json", selection)
    write_json(
        run_dir / "training_run.json",
        {
            "condition": condition,
            "smoke": smoke,
            "model": {"id": model_id, "revision": revision},
            "effective_config": json.loads(config.model_dump_json()),
            "student_content_sha256": student_manifest["student_content_sha256"],
            "train_ids_sha256": digest([r["id"] for r in rows]),
            "train_examples": len(rows),
            "validation_examples": len(validation),
            "max_train_sequence_tokens": max(lengths),
            "optimizer_steps": result.global_step,
            "train_loss": result.training_loss,
            "train_seconds": round(train_seconds, 1),
            "log_history": trainer.state.log_history,
            "selection": selection,
            "environment": environment(),
            "provenance": project_provenance(root),
        },
    )
    return selection
