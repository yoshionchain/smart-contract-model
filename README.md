# Synthetic Audit Distillation

A university NLP experiment in rationale distillation: does training a small model
(Qwen3-4B-Instruct-2507) on a large model's explanations help it judge reentrancy in
real Solidity code, and are its own explanations grounded? A teacher (GPT-6 Sol via
Codex CLI) analyses each training example without seeing its label; only reports whose
verdict matches the human label are kept. The student is fine-tuned with QLoRA on
labels only, on analysis-then-verdict reports, and on the same reports verdict-first,
and compared with the base model, lexical baselines and the teacher.

**Status:** the dataset is built and the teacher runner is ready (checked with mocks and
dry runs; no teacher call yet). The pilot, training and evaluation come next — see
[todo.md](todo.md). [SPEC.md](SPEC.md) is the detailed guideline and
holds the decision log.

## Setup

Python 3.12 and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked
uv run ruff check src scripts
```

## Build the dataset

```bash
uv run python scripts/fetch_data.py                               # pinned sources
HF_HUB_OFFLINE=1 uv run python scripts/build_dataset.py --stage inventory
uv run python scripts/validate_dataset.py
uv run python scripts/build_dataset.py --stage release
```

- `fetch_data.py` clones the seven pinned upstream snapshots into `data/raw/`
  (see [`configs/project.yaml`](configs/project.yaml)). It refuses dirty checkouts
  and revision mismatches.
- `inventory` (a few minutes) reads every source, blanks comments, resolves scopes,
  records every native judgment and builds leakage groups in
  `data/processed/inventory/`. It needs the pinned tokenizer; drop
  `HF_HUB_OFFLINE=1` on the first run to download it (no model weights).
- `validate_dataset.py` re-checks the inventory mechanically.
- `release` (seconds; [`configs/release.yaml`](configs/release.yaml)) selects
  upstream-reviewed labels, splits by group and balances each split by matched
  sampling. It writes `train`/`validation`/`test.parquet` and
  `external_smartbugs.parquet` to `data/processed/release/`, each row with its exact
  model input.

Raw and processed data stay local (gitignored). Small manifests and statistics are
committed in [`data/manifests/`](data/manifests/). Both build stages reproduce their
content fingerprints byte-for-byte.

## Teacher reports

```bash
HF_HUB_OFFLINE=1 uv run python scripts/generate_teacher.py --split train --pilot --dry-run
uv run python scripts/generate_teacher.py --split train --pilot     # uses Codex allowance
uv run python scripts/generate_teacher.py --split train             # and --split validation
uv run python scripts/generate_teacher.py --split test --ceiling    # once, for the ceiling row
```

The teacher is GPT-6 Sol through Codex CLI 0.156.1 on a ChatGPT login (no API key;
[`configs/teacher.yaml`](configs/teacher.yaml)). Each call shows it one example, exactly as
the student sees it, and never the label, in a private Codex home and an empty directory
with all tools off. `--dry-run` makes no model call: it checks the CLI, login and
isolation, writes every prompt to `runs/teacher/<run>/dry-run/` and estimates usage.
Real runs append every call and report to `runs/teacher/<run>/` and resume after an
interruption or a subscription limit. A report is kept only if it is valid, within 480
tokens and agrees with the human label; `usage.json` has the agreement per collection
and label.

## Dataset

Each example is one scope (a function or a whole file) of a real contract, the full
comment-blanked source with numbered lines, and a PRESENT/ABSENT label from published
human annotations, following their SWC-107 convention: *does this scope make an
external call or ether transfer through which the recipient could re-enter the
contract before its state updates are complete?*

| Split | PRESENT | ABSENT | Groups (P / A) | Positives with line annotations |
| --- | ---: | ---: | ---: | ---: |
| Train | 134 | 134 | 110 / 133 | 62 |
| Validation | 27 | 27 | 25 / 27 | 9 |
| Test | 27 | 27 | 22 / 27 | 13 |
| SmartBugs external | 30 | — | — | 30 |

| Collection | PRESENT | ABSENT |
| --- | ---: | ---: |
| SCRUBD-CD (function scope) | 75 | 143 |
| DAppSCAN audited projects (positives only) | 69 | 0 |
| Salzano: SmartBugs-wild sample / ZEUS set (file scope) | 35 | 35 |
| ScBench (file scope) | 9 | 10 |

A group is a project with its known copies and clones; no group spans two splits,
and anything related to SmartBugs stays out of development. Only labels with a
documented human annotation protocol are used (CGT's tool-derived labels are not);
at most 3 examples per group and label are kept; every PRESENT example is matched
1:1 with an ABSENT one from the same collection, scope kind and Solidity version
where possible. Details and rationale: SPEC.md Sections 6 and 17.

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

- Labels are upstream human annotations under the broad SWC-107 convention and were
  not re-reviewed locally; a spot check found about a third doubtful under a strict
  exploitability reading. The teacher's disagreement rate gives a second estimate.
- ABSENT means "not this reentrancy pattern in this scope", never "secure".
- Mostly older Solidity (0.4); DAppSCAN contributes positives only; balanced test
  metrics do not reflect real-world prevalence.
- Only reentrancy is studied; results do not show general vulnerability detection.
