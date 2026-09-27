# AGENTS.md

## Project

University NLP project on rationale distillation: fine-tune a small model
(Qwen3-4B-Instruct-2507) to judge whether a real Solidity contract is reentrant and
to write a grounded analysis **before** its verdict. A label-blind teacher (GPT-6 Sol via
Codex CLI) writes the training reports. Deadline: 2026-09-30.

The paper (`paper/`) is the main deliverable; `paper/material.md` collects every number,
table and citation it needs. Record approved research changes in
`docs/decision-log.md`. Do not change datasets, labels, splits, models, schemas, metrics
or training settings without the owner's approval.

## Layout

- `src/audit_distill/data/` — fetch, comment blanking, grouping, split and balance
  (dataset build from the pinned Ca' Foscari benchmark).
- `src/audit_distill/teacher/` — isolated Codex runner (`codex.py`) and label-blind
  generation (`generate.py`); settings in `configs/teacher.yaml`, prompt in
  `configs/prompts/`.
- `src/audit_distill/student/` — student chat formatting (shared cohort, three conditions,
  eval inputs); `src/audit_distill/payload.py` renders the one shared model input.
- `src/audit_distill/training/` — LoRA training (BF16) with checkpoint selection (`train.py`)
  and the Colab CLI workflow (`colab.py`); `src/audit_distill/inference.py` holds shared
  greedy generation, strict verdict parsing and macro-F1.
- `src/audit_distill/evaluation/` — test predictions for all modes (`predict.py`, GPU) and
  scoring with baselines, teacher ceiling, group bootstrap and grounding (`score.py`);
  results in `results/` (committed).
- `src/audit_distill/scoped_reports.py` — report and teacher answer schemas, field
  orders, strict parsing and label-blind report validation.
- `scripts/` — thin CLI entry points.
- `configs/` — all settings (`data.yaml`, `teacher.yaml`, `training.yaml`, prompts).
- `schemas/` — report and teacher answer schemas (export with
  `uv run python -m audit_distill.data.schema`).
- `data/manifests/` — small committed build manifests and statistics.
- `data/raw/`, `data/processed/`, `runs/` — local only, gitignored.

## Commands

```bash
uv sync --locked
uv run ruff check src scripts
uv run python scripts/fetch_data.py
HF_HUB_OFFLINE=1 uv run python scripts/build_dataset.py
HF_HUB_OFFLINE=1 uv run python scripts/generate_teacher.py --split train --pilot --dry-run
HF_HUB_OFFLINE=1 uv run python scripts/build_student_dataset.py
uv sync --group train && CUDA_VISIBLE_DEVICES= uv run python scripts/train.py --condition report --smoke
uv run python scripts/colab.py {up,setup,train,predict,faithfulness,watch,status,fetch,down}   # GPU: approval first
uv run python scripts/evaluate.py
```

`--dry-run` never calls the model. Without it, `generate_teacher.py` spends Codex
allowance: run it only after approval (see Resource gates).

## How to work

- Build things in the simplest reliable way; small typed modules, no frameworks,
  databases, services or notebooks-only code.
- Python 3.12, `uv` only (`pyproject.toml` + `uv.lock`), Pydantic for records and
  configs, `pathlib`, standard `logging`, `tqdm` for progress.
- Settings live in YAML configs, not constants scattered in code.
- Keep outputs deterministic and hashed; record seeds, versions and effective configs.
- Keep README commands in sync with the actual CLI. Do not over-document.

## Research rules

- Labels are the benchmark's expert labels under its written definition, used as-is.
  Never relabel, never present them as locally reviewed, and never count assistant
  checks as human validation. ABSENT never means secure.
- Never mix sources with different labelling conventions (why v2.3 was abandoned).
- Exclude, never keep or edit, contracts whose code reveals the label (bug-injection
  artifacts); no clone group or scenario family may cross splits.
- Comments are blanked without moving lines; line numbers must stay exact.
- Overlength sources are excluded and counted, never truncated.
- Test data never tunes prompts, preprocessing, splits or training.
- Never cherry-pick teacher outputs beyond the declared acceptance rules.
- No fabricated or placeholder results; paper tables come from real result files.

## Teacher (locked)

- Codex CLI 0.156.1, `codex exec`, model `gpt-6-sol`, reasoning `medium`, verbosity `low`,
  ChatGPT subscription only — no OpenAI API, no fallback model.
- Private `CODEX_HOME` (login copy only), ephemeral, read-only sandbox, no approvals,
  empty temp dir per call, tools/web/MCP and inherited instructions disabled, offline
  `prompt-input` preflight; any tool event rejects the call.
- Label-blind: the teacher sees only the payload; a report is accepted only if its
  verdict matches the benchmark label. Rejected queries leave all SFT cohorts with
  their matched partner.
- The teacher runs on test data only once, for the ceiling row, after the prompt is
  frozen and with separate approval; its test outputs never feed anything else.
- One query per call, at most one retry for invalid output, resumable, usage logged.

## Resource gates

- Never spend Codex allowance without explicit approval for that run. Before the pilot
  (≤ 6 training queries) and each production run, show the exact command and expected
  usage, then wait.
- Never start a real Colab/GPU job without explicit approval. Local CPU smoke runs on
  tiny inputs are fine.
- If a subscription limit blocks work, stop and report.

## Git

- Commit only when asked. Never commit raw data, processed data, weights, checkpoints,
  run caches, Codex/ChatGPT/HF credentials or other secrets.
