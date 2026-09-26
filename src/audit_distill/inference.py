"""Greedy generation, strict verdict parsing and macro-F1, shared by training and evaluation.

A verdict answer must be exactly PRESENT or ABSENT after trimming whitespace; a report
must be strict JSON in the condition's field order (`parse_report`). Anything else is
INVALID, which never counts as correct. Outputs are never repaired.
"""

import json
from pathlib import Path
from typing import Any, Literal

from audit_distill.scoped_reports import parse_report

Format = Literal["label", "report", "report_vf"]
ORDER = {"report": "analysis_first", "report_vf": "verdict_first"}
POLARITIES = ("PRESENT", "ABSENT")


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def generate(
    model: Any, tokenizer: Any, rows: list[dict], max_new_tokens: int, batch_size: int
) -> list[str]:
    """Greedy continuations of each row's chat prompt, in row order."""
    import torch

    tokenizer.padding_side = "left"
    texts = [
        tokenizer.apply_chat_template(r["prompt"], tokenize=False, add_generation_prompt=True)
        for r in rows
    ]
    outputs: list[str] = []
    for start in range(0, len(texts), batch_size):
        batch = tokenizer(
            texts[start : start + batch_size],
            return_tensors="pt",
            padding=True,
            add_special_tokens=False,
        ).to(model.device)
        with torch.no_grad():
            generated = model.generate(
                **batch,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=tokenizer.pad_token_id,
            )
        new = generated[:, batch["input_ids"].shape[1] :]
        outputs += tokenizer.batch_decode(new, skip_special_tokens=True)
    return outputs


def verdict(fmt: Format, raw: str, line_count: int) -> str:
    """PRESENT, ABSENT or INVALID for one raw model output."""
    if fmt == "label":
        answer = raw.strip()
        return answer if answer in POLARITIES else "INVALID"
    try:
        return parse_report(raw, line_count=line_count, order=ORDER[fmt]).verdict
    except ValueError:
        return "INVALID"


def macro_f1(gold: list[str], predicted: list[str]) -> float:
    """Binary macro-F1 over the gold labels; INVALID is a miss for its gold label."""
    scores = []
    for label in POLARITIES:
        tp = sum(g == label and p == label for g, p in zip(gold, predicted, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, predicted, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, predicted, strict=True))
        scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(scores) / len(scores)
