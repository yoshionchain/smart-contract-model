# Synthetic Audit Distillation

A university NLP experiment in rationale distillation: does training a small model
(Qwen3-4B-Instruct-2507) on a large model's explanations help it judge whether a real
Solidity contract is reentrant, and are its own explanations grounded? A teacher
(GPT-6 Sol via Codex CLI) analyses each training contract without seeing its label;
only reports whose verdict matches the expert label are kept. The student is
fine-tuned with LoRA on labels only, on analysis-then-verdict reports, and on the
same reports verdict-first, and compared with the base model, lexical baselines and
the teacher.

**Status:** the dataset, teacher reports and student training data are built; training
is next — see [todo.md](todo.md). [SPEC.md](SPEC.md) is the detailed guideline
and holds the decision log.

## Setup

Python 3.12 and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked
uv run ruff check src scripts
```

## Build the dataset

```bash
uv run python scripts/fetch_data.py                      # pinned benchmark revision
HF_HUB_OFFLINE=1 uv run python scripts/build_dataset.py  # about a minute
```

- `fetch_data.py` clones the pinned benchmark into `data/raw/` and refuses dirty
  checkouts and revision mismatches.
- `build_dataset.py` ([`configs/data.yaml`](configs/data.yaml)) blanks comments,
  numbers lines, applies the exclusions, groups clones and scenario families, splits
  by group and balances each split. It writes `train`/`validation`/`test.parquet` to
  `data/processed/release/`, each row with its exact model input. It needs the pinned
  tokenizer; drop `HF_HUB_OFFLINE=1` on the first run to download it (no weights).

Raw and processed data stay local (gitignored). The manifest and statistics are
committed in [`data/manifests/`](data/manifests/); the build reproduces its content
fingerprint byte-for-byte.

## Dataset

Each example is one whole contract, its comment-blanked source with numbered lines,
and a PRESENT/ABSENT label from the [Ca' Foscari reentrancy benchmarks](https://github.com/ca-foscari-reentrancy-research-group/reentrancy-detection-llms)
(Ressi et al., *Reentrancy Detection in the Age of LLMs*, DSN 2026). Three experts
labelled every contract under one operational definition: *an external call to code an
attacker may control, a state update after it that depends on the attacker, and a
final state reachable by re-entering that the same calls without re-entry could not
reach.* The same definition and its assumptions are shown to every model.

| Split | PRESENT | ABSENT | Groups (P / A) |
| --- | ---: | ---: | ---: |
| Train | 78 | 78 | 41 / 63 |
| Validation | 17 | 17 | 10 / 14 |
| Test | 30 | 30 | 24 / 13 |

| Collection | Pairs (train / val / test) | Content |
| --- | ---: | --- |
| Aggregated Benchmark | 35 / 8 / 14 | Real deployed contracts, mostly Solidity 0.4 |
| RSD | 43 / 9 / 16 | Handcrafted Solidity 0.8 scenarios in reentrant/safe variants |

Excluded and counted: bug-injected contracts whose artifacts reveal the label
(SolidiFI `bug_re_ent…` names, HuangGai's inserted calls), sources over 6,000 tokens,
duplicates, and surplus safe contracts after balancing. A group joins exact clones, near
clones and RSD scenario families; no group spans two splits. Each split is balanced
1:1 within each collection, matching Solidity versions where possible. Details:
SPEC.md Sections 4–6 and 17.

## Teacher reports

```bash
HF_HUB_OFFLINE=1 uv run python scripts/generate_teacher.py --split train --pilot --dry-run
uv run python scripts/generate_teacher.py --split train --pilot     # uses Codex allowance
uv run python scripts/generate_teacher.py --split train             # and --split validation
uv run python scripts/generate_teacher.py --split test --ceiling    # once, for the ceiling row
```

The teacher is GPT-6 Sol through Codex CLI 0.156.1 on a ChatGPT login (no API key;
[`configs/teacher.yaml`](configs/teacher.yaml)). Each call shows it one contract, exactly
as the student sees it, and never the label, in a private Codex home and an empty
directory with all tools off. `--dry-run` makes no model call: it checks the CLI, login
and isolation, writes every prompt to `runs/teacher/<run>/dry-run/` and estimates usage.
Real runs append every call and report to `runs/teacher/<run>/` and resume after an
interruption or a subscription limit. A report is kept only if it is valid, within 480
tokens and agrees with the expert label; `usage.json` has the agreement per collection
and label.

## Student training data

```bash
HF_HUB_OFFLINE=1 uv run python scripts/build_student_dataset.py
```

Writes `data/processed/student/` from the release and the train teacher run
([`configs/student.yaml`](configs/student.yaml)): the same 140 accepted train contracts
(70 pairs) for Label-SFT, Report-SFT and Report-SFT-VF in one seeded order, as
prompt/completion chat records; every validation and test contract as evaluation
prompts for each format; and `shared_cohort.json`. A pair leaves together if the teacher
disagreed with either label. The build is reproducible and its manifest and statistics
are committed in `data/manifests/`.

## Training

```bash
uv sync --group train                                              # torch, TRL, PEFT
CUDA_VISIBLE_DEVICES= uv run python scripts/train.py --condition report --smoke  # tiny CPU check
uv run python scripts/colab.py up          # rent an H100 on Colab, upload code + student data
uv run python scripts/colab.py train       # label, report, report-vf as a background job
uv run python scripts/colab.py status      # progress
uv run python scripts/colab.py sync        # upload newer code without touching runs/
uv run python scripts/colab.py predict     # test predictions for all five modes
uv run python scripts/colab.py fetch       # adapters, selection, predictions, logs into runs/
uv run python scripts/colab.py down        # release the VM
uv run python scripts/evaluate.py          # baselines, teacher ceiling, metrics -> results/
```

LoRA settings (BF16 base, no quantization) are in [`configs/training.yaml`](configs/training.yaml). Each condition
trains on the same 140 contracts; after training, every epoch's adapter answers all 34
validation contracts and the best validation macro-F1 is kept. The `--smoke` run uses a
tiny random model only to exercise the code; it is never a result.

## The report format

Reports are one JSON object; Report-SFT writes the analysis first:

```json
{"analysis": "Line 42 sends ether before line 47 updates the balance ...",
 "verdict": "PRESENT",
 "location": {"start_line": 42, "end_line": 47, "function": "withdraw"}}
```

ABSENT reports have `"location": null`. The verdict-first ablation uses the same
fields in the order `verdict, analysis, location`.
`src/audit_distill/scoped_reports.py` validates reports strictly;
[`schemas/audit_report.schema.json`](schemas/audit_report.schema.json) is its export.

## Limitations

- One benchmark and one definition of reentrancy; ABSENT means "not reentrant by this
  definition", never "secure".
- A small test set (60 contracts, 30 pairs); RSD contracts are handcrafted and short,
  and the real contracts are mostly old Solidity 0.4.
- Only reentrancy is studied; results do not show general vulnerability detection.
- An earlier mixed-source dataset (v2.3) was abandoned because its sources labelled
  reentrancy by conflicting conventions; the teacher agreed with only 62% of its labels
  ([`data/manifests/teacher_v2.3_mixed_sources.json`](data/manifests/teacher_v2.3_mixed_sources.json)).
