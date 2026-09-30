# Distilling Explanations, Not Just Labels

*Can Small Language Models Learn to Justify Smart Contract Vulnerability Judgments?*

University NLP project (Übung Informationslinguistik 2, Universität Regensburg). The paper:
[`paper/paper.pdf`](paper/paper.pdf).

Large language models can judge whether code is vulnerable and explain why, but they are
expensive to run. This project tests **rationale distillation**: a large teacher
(GPT-6 Sol) writes a short, line-citing analysis of each training contract *without
seeing its label*; analyses that reach the expert label are kept; a 4B student
(Qwen3-4B-Instruct-2507) is fine-tuned with LoRA on these explanations and, for
comparison, on labels alone. The task is binary: does a smart contract contain a
**reentrancy** vulnerability — does it call out to another contract before updating its
own records, so that the callee can call back and exploit the stale state?

## Results at a glance

Test set: 60 contracts (30 vulnerable, 30 safe; 28 real-world, 32 hand-written minimal
pairs). Macro-F1; students: mean (± SD) over three training seeds, other rows: one run.

| Model | All | Real-world | Minimal pairs |
| --- | ---: | ---: | ---: |
| Teacher (GPT-6 Sol, upper bound) | 0.933 | 0.928 | 0.937 |
| Student, labels + explanations (multi-task) | **0.809 ± 0.019** | 0.940 | 0.677 |
| Student, explanation then verdict | 0.793 ± 0.056 | 0.866 | **0.720** |
| Student, verdict then explanation | 0.777 ± 0.026 | 0.904 | 0.657 |
| Student, labels only | 0.768 ± 0.030 | 0.928 | 0.595 |
| TF-IDF + logistic regression | 0.707 | 0.854 | 0.573 |
| Base model, explanation then verdict | 0.653 | 0.928 | 0.304 |

- Training on explanations helps on average, most on the hard minimal pairs.
- The student's explanations are grounded: 94.6–98.5% of cited line numbers point at
  code, and the conclusion always states the model's own verdict (base model: 15%).
- The verdict causally depends on the explanation: given the analysis it wrote for the
  matched opposite contract, every analysis-first model follows that analysis (100%).
- A label-blind teacher is a consistency check for datasets: on an earlier mix of five
  sources it agreed with only 62.5% of labels (conflicting labelling conventions), on
  the single expert-labelled benchmark with 94.9%.

Full tables: [`results/run2-multi/results.md`](results/run2-multi/results.md) (final),
[`results/run1-original/results.md`](results/run1-original/results.md) (first run, 3
epochs). Why the project evolved this way: [`docs/decision-log.md`](docs/decision-log.md).

## Repository layout

```text
configs/           all settings: data.yaml, teacher.yaml, student.yaml, training.yaml,
                   evaluation.yaml; prompts/ (teacher and the three student formats)
src/audit_distill/ the Python package
  data/            fetch the benchmark, blank comments, group clones, split, balance
  teacher/         isolated Codex CLI runner and label-blind report generation
  student/         chat-formatted training and evaluation data for all conditions
  training/        LoRA training with checkpoint selection; Colab CLI workflow
  evaluation/      test predictions, faithfulness test, scoring and baselines
  payload.py       the one rendering of a model input (shared by teacher and student)
  scoped_reports.py  report schema, strict parsing and validation
  inference.py     greedy generation, verdict parsing, macro-F1
scripts/           one thin command per pipeline stage (see below)
schemas/           JSON schemas of the report and the teacher answer
data/manifests/    committed hashes and statistics of every data build
results/           committed metrics, tables, per-model test predictions and
                   per-epoch validation scores (training/)
docs/              decision log
paper/             the paper (PDF)
```

The pipeline runs in stages; each stage reads the previous stage's hashed output:

```text
benchmark (pinned) ─► build_dataset ─► generate_teacher ─► build_student_dataset
      ─► train (GPU) ─► predict, faithfulness (GPU) ─► evaluate ─► results/
```

## Installation

- **Python 3.12** and [**uv**](https://docs.astral.sh/uv/) (dependency management).
- **Git** (the benchmark is fetched at a pinned revision).
- For teacher reports only: [Codex CLI](https://github.com/openai/codex) **0.156.1**,
  logged in with a ChatGPT subscription (`codex login`).
- For training and GPU inference only: the
  [Google Colab CLI](https://pypi.org/project/google-colab-cli/) (`uv tool install
  google-colab-cli`, logged in) and Colab compute units for an A100; or any local CUDA
  GPU with bf16 support (then run `scripts/train.py` etc. directly).

```bash
git clone https://github.com/yoshionchain/smart-contract-model.git && cd smart-contract-model
uv sync --locked                 # data, teacher and evaluation dependencies
uv sync --locked --group train   # adds PyTorch (CUDA 12.6), Transformers, TRL, PEFT
uv run ruff check src scripts    # optional lint
```

Main libraries: Transformers 4.57, TRL 1.14, PEFT 0.21, PyTorch 2.14, scikit-learn,
pyarrow, Pydantic. The first run downloads the Qwen3 tokenizer/model from Hugging Face
(no token needed).

## Usage: reproduce the experiment

Each command writes to `data/processed/` or `runs/` (both local, gitignored) and records
hashes, seeds, versions and the effective config.

```bash
# 1. Data (CPU, about a minute)
uv run python scripts/fetch_data.py
uv run python scripts/build_dataset.py

# 2. Teacher reports (Codex CLI; costs subscription usage; --dry-run makes no call)
uv run python scripts/generate_teacher.py --split train --pilot --dry-run
uv run python scripts/generate_teacher.py --split train
uv run python scripts/generate_teacher.py --split validation
uv run python scripts/generate_teacher.py --split test --ceiling   # upper bound only

# 3. Student training data (CPU)
uv run python scripts/build_student_dataset.py

# 4. Training and GPU inference on a Colab A100
uv run python scripts/colab.py up                        # rent, upload, install
uv run python scripts/colab.py train                     # four conditions, seed 42
uv run python scripts/colab.py watch                     # poll, download finished runs
uv run python scripts/colab.py predict                   # test predictions, all modes
uv run python scripts/colab.py watch
uv run python scripts/colab.py followup --seeds 43 44    # seeds, their predictions,
uv run python scripts/colab.py watch                     #   and the faithfulness test
uv run python scripts/colab.py down                      # release the VM

# 5. Scoring (CPU): baselines, teacher ceiling, bootstrap intervals -> results/
uv run python scripts/evaluate.py
```

On a local GPU, steps 4 map to `scripts/train.py --condition {label,report,report-vf,multi}
[--seed N]`, `scripts/predict.py [--seed N]` and `scripts/faithfulness.py`. A CPU smoke
test of the training code: `CUDA_VISIBLE_DEVICES= uv run python scripts/train.py
--condition report --smoke` (tiny random model; not a result).

## Data and labels

Contracts and labels come from the
[Ca' Foscari reentrancy benchmarks](https://github.com/ca-foscari-reentrancy-research-group/reentrancy-detection-llms)
(Ressi et al. 2026): 432 real-world contracts re-labelled by three experts under one
written definition, and 143 hand-written scenarios in vulnerable/safe variants. Labels
are used as-is. Excluded and counted: contracts whose code reveals the label
(bug-injection artifacts), sources over 6,000 tokens and duplicates. Contracts that are
clones or belong to the same scenario family never cross splits; each split is balanced
1:1. Final split: 78/78 train, 17/17 validation, 30/30 test. Raw and processed data stay
local; hashes and statistics are in [`data/manifests/`](data/manifests/).

## Limitations

One vulnerability type and one benchmark; a small test set (60 contracts), so intervals
are wide; the real-world code is mostly old Solidity; the teacher filter may keep easier
training examples; no human evaluation of report quality. ABSENT means "not reentrant by
this definition", never "secure".
