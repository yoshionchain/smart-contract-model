# AGENTS.md

## Project

University NLP project on rationale distillation: fine-tune a small model
(Qwen3-4B-Instruct-2507) to judge reentrancy in a given scope of real Solidity code and
to write a grounded analysis **before** its verdict. A label-blind teacher (GPT-6 Sol via
Codex CLI) writes the training reports. Deadline: 2026-09-30.

`SPEC.md` is the guideline and holds the decision log. It is not sacred: propose a
change when it clearly improves the project, and record approved changes in its
decision log (Section 17). Do not change datasets, labels, splits, models, schemas,
metrics or training settings without the owner's approval.

Current state and next steps: `todo.md`.

## Layout

- `src/audit_distill/data/` — ingestion, inventory, grouping, release (dataset build).
- `src/audit_distill/teacher/` — isolated Codex runner (`codex.py`) and label-blind
  generation (`generate.py`); settings in `configs/teacher.yaml`, prompt in
  `configs/prompts/`.
- `src/audit_distill/scoped_reports.py` — report and teacher answer schemas, field
  orders, strict parsing and label-blind report validation.
- `scripts/` — thin CLI entry points.
- `configs/` — all settings (sources, taxonomy, release, training).
- `schemas/` — report and teacher answer schemas (export with
  `uv run python -m audit_distill.data.schema`).
- `data/manifests/` — small committed build manifests and statistics.
- `data/raw/`, `data/processed/`, `runs/` — local only, gitignored.

## Commands

```bash
uv sync --locked
uv run ruff check src scripts
uv run python scripts/fetch_data.py
HF_HUB_OFFLINE=1 uv run python scripts/build_dataset.py --stage inventory
uv run python scripts/validate_dataset.py
uv run python scripts/build_dataset.py --stage release
HF_HUB_OFFLINE=1 uv run python scripts/generate_teacher.py --split train --pilot --dry-run
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

- Labels are upstream human annotations used as-is (SWC-107 convention). Never
  relabel, never present them as locally reviewed, and never count assistant checks
  as human validation.
- UNKNOWN, missing labels, tool silence and other weaknesses' labels are never ABSENT.
  A negative function is never lifted to a whole file. ABSENT never means secure.
- No project, hash, clone group or SmartBugs-related code may cross splits.
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
  verdict matches the upstream label. Rejected queries leave all SFT cohorts with
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
