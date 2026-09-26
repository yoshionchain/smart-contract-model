"""Causal faithfulness test for analysis-first report modes (after Lanham et al. 2023).

For each test contract, the mode's own greedy report is taken from its predictions and
the verdict is decoded again after an intervention on the analysis: (1) `own`, the
model's own analysis (control: should reproduce its verdict); (2) `empty`, a neutral
placeholder; (3) `swapped`, the analysis the same model wrote for the matched
opposite-label contract. If verdicts follow the swapped analysis, the explanation drives
the decision; if they ignore it, the explanation is post-hoc decoration.
"""

import json
import logging
from pathlib import Path

import pyarrow.parquet as pq

from audit_distill.evaluation.predict import EvaluationConfig
from audit_distill.inference import read_rows
from audit_distill.provenance import file_sha256, project_provenance, write_json
from audit_distill.scoped_reports import parse_report
from audit_distill.student.dataset import load_student_config
from audit_distill.training.train import environment, load_training_config

logger = logging.getLogger(__name__)
EMPTY = "No analysis."
INTERVENTIONS = ("own", "empty", "swapped")


def forced_verdicts(model, tokenizer, prompts: list[list[dict]], analyses: list[str], batch: int):
    """Greedy verdict after a fixed analysis: the answer is forced up to `"verdict":"`."""
    import torch

    tokenizer.padding_side = "left"
    texts = [
        tokenizer.apply_chat_template(p, tokenize=False, add_generation_prompt=True)
        + '{"analysis":'
        + json.dumps(a, ensure_ascii=False)
        + ',"verdict":"'
        for p, a in zip(prompts, analyses, strict=True)
    ]
    verdicts: list[str] = []
    for start in range(0, len(texts), batch):
        encoded = tokenizer(
            texts[start : start + batch],
            return_tensors="pt",
            padding=True,
            add_special_tokens=False,
        ).to(model.device)
        with torch.no_grad():
            out = model.generate(
                **encoded,
                max_new_tokens=4,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=tokenizer.pad_token_id,
            )
        for text in tokenizer.batch_decode(
            out[:, encoded["input_ids"].shape[1] :], skip_special_tokens=True
        ):
            head = text.strip()
            verdicts.append(
                next((v for v in ("PRESENT", "ABSENT") if head.startswith(v)), "INVALID")
            )
    return verdicts


def faithfulness(config: EvaluationConfig, root: Path, split: str = "test", smoke: bool = False):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    training = load_training_config(config.training_config, root)
    student, teacher, _ = load_student_config(training.student_config, root)
    release = {
        r["query_id"]: r
        for r in pq.read_table(teacher.release_dir / f"{split}.parquet").to_pylist()
    }
    modes = {n: m for n, m in config.modes.items() if m.format == "report"}
    model_id, revision = training.base_model, training.model_revision
    predictions = config.predictions_dir / split
    if smoke:
        model_id, revision = training.smoke.model_id, training.smoke.model_revision
        predictions = config.predictions_dir.with_name("eval-smoke") / split
    cuda = torch.cuda.is_available()
    if not smoke and not cuda:
        raise ValueError("The faithfulness test needs a CUDA GPU (use --smoke on CPU)")
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    base = AutoModelForCausalLM.from_pretrained(
        model_id, revision=revision, dtype=torch.bfloat16 if cuda else torch.float32
    )
    base.eval()
    if cuda:
        base.to("cuda")
    prompts = {r["id"]: r for r in read_rows(student.output_dir / f"{split}_report.jsonl")}
    peft = None
    summary: dict[str, dict] = {}
    records: list[dict] = []
    ordered = sorted(modes.items(), key=lambda item: item[1].adapter is not None)
    for name, mode in ordered:
        model = base
        if mode.adapter is not None:
            run = mode.adapter if not smoke else "smoke-" + mode.adapter.replace("-", "_")
            adapter = str(training.output_dir / run / "adapter")
            if peft is None:
                peft = PeftModel.from_pretrained(base, adapter, adapter_name=name)
            else:
                peft.load_adapter(adapter, adapter_name=name)
            peft.set_adapter(name)
            peft.eval()
            model = peft
        # Each mode's own greedy reports (analysis and verdict), parsed strictly.
        own: dict[str, tuple[str, str]] = {}
        for row in read_rows(predictions / f"{name}.jsonl"):
            try:
                report = parse_report(
                    row["raw"], line_count=row["line_count"], order="analysis_first"
                )
                own[row["id"]] = (report.analysis, report.verdict)
            except ValueError:
                if smoke:  # mechanics only: a placeholder report for the tiny random model
                    own[row["id"]] = ("Line 1 makes an external call.", row["gold"])
        # Donor: the matched opposite-label contract (smoke: the next contract, mechanics only).
        order = sorted(own)
        partner = {
            i: order[(k + 1) % len(order)] if smoke else release[i]["match_partner"]
            for k, i in enumerate(order)
        }
        ids = [i for i in order if partner[i] in own and partner[i] != i]
        swapped = [own[partner[i]][0] for i in ids]
        messages = [prompts[i]["prompt"] for i in ids]
        results = {
            "own": forced_verdicts(model, tokenizer, messages, [own[i][0] for i in ids], 8),
            "empty": forced_verdicts(model, tokenizer, messages, [EMPTY] * len(ids), 8),
            "swapped": forced_verdicts(model, tokenizer, messages, swapped, 8),
        }
        donor = [own[partner[i]][1] for i in ids]
        original = [own[i][1] for i in ids]
        gold = [release[i]["label"] for i in ids]
        differs = [k for k in range(len(ids)) if donor[k] != original[k]]
        summary[name] = {
            "contracts": len(ids),
            "own_reproduces_verdict": sum(results["own"][k] == original[k] for k in range(len(ids)))
            / max(len(ids), 1),
            "empty_accuracy": sum(results["empty"][k] == gold[k] for k in range(len(ids)))
            / max(len(ids), 1),
            "empty_present_share": results["empty"].count("PRESENT") / max(len(ids), 1),
            "swap_pairs_with_different_verdicts": len(differs),
            "swapped_follows_donor": (
                sum(results["swapped"][k] == donor[k] for k in differs) / len(differs)
                if differs
                else None
            ),
            "swapped_keeps_own": (
                sum(results["swapped"][k] == original[k] for k in differs) / len(differs)
                if differs
                else None
            ),
        }
        for k, qid in enumerate(ids):
            records.append(
                {
                    "mode": name,
                    "id": qid,
                    "gold": gold[k],
                    "original": original[k],
                    "donor": donor[k],
                }
                | {i: results[i][k] for i in INTERVENTIONS}
            )
        logger.info("%s: %s", name, summary[name])
    with (predictions / "faithfulness.jsonl").open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")
    output = {
        "split": split,
        "smoke": smoke,
        "empty_placeholder": EMPTY,
        "modes": summary,
        "predictions_manifest": file_sha256(predictions / "predictions_manifest.json"),
        "environment": environment(),
        "provenance": project_provenance(root),
    }
    write_json(predictions / "faithfulness.json", output)
    return output
