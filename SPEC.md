# Synthetic Audit Distillation — Specification

**Version:** 3.0 (2026-09-26) · **Status:** dataset, teacher reports and student data built; training next ·
**Deadline:** 2026-09-30 23:59 · **Type:** university NLP project, ACL-format paper

This is the project guideline. It may change when a change clearly improves the
project; record every approved change in the decision log (Section 17).

---

## 1. Goal and research questions

This is **rationale distillation** for a code-understanding task: does training a
small language model on a large model's natural-language explanations help it judge
whether a real Solidity contract is reentrant, and are its own explanations grounded?
Code and labels come from one expert-verified benchmark with one written definition.
The teacher writes explanations only; it never creates code or changes labels. Related
work: Distilling Step-by-Step (Hsieh et al. 2023), Ho et al. 2023, Magister et al.
2023, e-SNLI (Camburu et al. 2018), explanation faithfulness (Jacovi & Goldberg 2020;
Wiegreffe & Marasović 2021), reentrancy benchmarks (Ressi et al. 2026).

- **RQ1 (main) — Do rationales help?** Does fine-tuning on teacher analyses followed by
  the verdict (Report-SFT) improve verdicts over fine-tuning on labels alone
  (Label-SFT)? Floors: the base model and lexical baselines; ceiling: the teacher.
  **Order ablation:** the same reports with the verdict first (Report-SFT-VF) separate
  "reasoning before deciding" from "extra training signal". **Multi-task (run 2):**
  training on both the label and the report of each contract (Multi-SFT, Distilling
  Step-by-Step) and answering in label mode tests rationales as auxiliary signal.
- **RQ2 — Are the student's rationales grounded and faithful?** Do cited line numbers
  exist and point at code, and does the analysis support the model's own verdict
  (automatic metrics; optional blinded human rating)? Agreement with teacher text is
  not correctness.
- **RQ3 — Do the LLM and the expert labels agree?** How often does the label-blind
  teacher agree with the benchmark labels, per collection and label, and what kinds of
  cases does it reject? Contrast: on the earlier mixed-source release (v2.3) it agreed
  only 62% (Section 17), because the sources used conflicting conventions.

Hypotheses (directional; negative or mixed results are valid): H1 all SFT conditions
beat their base-model format; H2 Report-SFT ≥ Label-SFT; H3 open: analysis-first may
beat verdict-first by reasoning before deciding, or lose when a flawed analysis
propagates; H4 Report-SFT analyses are better grounded than Base-Report analyses.
Completion-token exposure differs between Label-SFT and the report conditions (not
between the two report orders); report it. One seed and a small test set restrict
claims about small differences.

**Out of scope:** other vulnerability classes, bug-injected code, scanner votes as
gold, LLM relabeling of any data, function-level labels or line localization (the
benchmark labels whole contracts), RAG, agents, extra student architectures,
hyperparameter sweeps, deployment, BLEU/ROUGE as correctness.

## 2. Terms

- **Query:** one check + one whole contract source (numbered lines) + assumptions.
- **PRESENT / ABSENT:** the benchmark's reentrant / safe label under its definition.
  ABSENT means "not reentrant by this definition", never "secure".
- **Collection:** `aggregated` (real deployed contracts) or `rsd` (handcrafted scenarios).
- **Group:** contracts connected by an exact token skeleton, a near clone or an RSD
  scenario family; the unit of splitting and uncertainty.
- **Teacher:** GPT-6 Sol via Codex CLI. **Student:** Qwen3-4B-Instruct-2507.
  **Label-SFT / Report-SFT / Report-SFT-VF / Multi-SFT:** its adapters (verdict only;
  analysis-first report; the same reports verdict-first; both label and report tasks). **Base-Label / Base-Report:**
  the unchanged model with the verdict and report prompts.

## 3. The check

The definition and assumptions shown to every model follow the benchmark's operational
definition and labelling procedure (Ressi et al. 2026, Section IV-C):

> Reentrancy: the contract makes an external call to code an attacker may control;
> after that call returns, it performs a state update that depends on the attacker's
> interaction; and by re-entering the contract during the call, the attacker can drive
> it to a final state that no sequence of the same calls without re-entry could reach.

Assumptions: (1) any address an untrusted caller can supply or influence, and any
contract whose code is not in the source (such as a token), may run attacker code;
(2) `transfer` and `send` forward only 2,300 gas and cannot be used to re-enter;
(3) state updates are writes to storage and delegatecalls; events, `require`, `assert`
and `revert` are not; (4) read-only reentrancy counts only when other code in the
source relies on a view function that returns inconsistent state during the call; the
automatic getters of public variables alone do not (as in the benchmark's read-only
scenarios, whose safe variants guard only the views other code uses).

Guards (mutexes, ordering) matter only through the third condition: re-entry must be
able to reach a divergent final state. A `nonReentrant` name is not proof of protection.

## 4. Source

| Source | Pinned revision | Content |
| --- | --- | --- |
| [Ca' Foscari reentrancy benchmarks](https://github.com/ca-foscari-reentrancy-research-group/reentrancy-detection-llms) | `d7c9496121931cff7c55b2047d18fb048fefe2cb` | Aggregated Benchmark (432 real contracts, 120 reentrant / 312 safe) and RSD (143 handcrafted Solidity 0.8 scenarios, 71 / 72) |

The Aggregated Benchmark merges CGT, HuangGai and ReentrancyStudy contracts; three
domain experts re-inspected all of them in several rounds under the definition above
(28 "reentrant" relabelled safe, 5 "safe" relabelled reentrant). RSD contracts were
written and labelled by the same procedure, in minimal reentrant/safe variants per
scenario family. Labels are contract-level (folders / file suffixes) and used as-is;
file names and paths never enter prompts. Licence: CC BY 4.0 per the paper; raw data
stays local (gitignored).

**Exclusions** (counted in `release_statistics.json`, never relabelled):

- **Bug-injection artifacts:** SolidiFI-injected contracts carry identifiers such as
  `bug_re_ent27` (31 reentrant, all excluded via the `_re_ent` pattern) and HuangGai
  contracts an inserted `x.call.value(1)("")` (21, excluded by origin). Both occur only
  on one label and would be shortcuts.
- **Overlength:** numbered source > 6000 tokens (23). **Duplicates:** identical token
  identity (14); conflicting duplicates would be excluded entirely (none).

## 5. Model input and records

- **Sanitization:** blank all comments, preserving length, CR/LF positions and quoted
  literals. Render lines as `0001 | ...`; no phantom final line.
- **Input payload** (identical for every model and condition): `check_id`, definition,
  scope (always the whole file), assumptions and the complete numbered source. It never
  contains file names, paths, origins, labels or collection names.
- **Hashes:** `model_input_sha256` = SHA-256 of the canonical payload;
  `code_identity_sha256` = lexical token identity, also the query ID (so rewording the
  definition never reshuffles the split). Hashes never rewrite input.
- **Budgets** (pinned tokenizer `Qwen/Qwen3-4B-Instruct-2507` @
  `cdbee75f17c01a7cc42f958dc650907174af0554`, no special tokens): numbered source
  ≤ **6000** tokens (longer sources are excluded, never truncated); full chat sequence
  ≤ **8192**; teacher report ≤ **480** tokens as canonical JSON (UTF-8, compact
  separators); inference allows **512** new tokens for reports and **16** for verdicts.
- **Records** are typed (Pydantic), persisted as Parquet/JSONL, never in a database.

## 6. Grouping, split and balance

`build_dataset.py` (settings in `configs/data.yaml`):

1. Read both collections; apply the exclusions of Section 4 and de-duplicate.
2. **Groups** (union-find): RSD scenario family (file name without `_ree1`/`_safe1`; a
   contract duplicated across families links all of them),
   exact full-source token skeleton (identifiers alpha-renamed, literals typed, pragmas
   ignored), near clones (≥ 100 skeleton tokens, length ratio ≥ 0.8, token 5-gram
   Jaccard ≥ 0.85, exact). No group crosses partitions.
3. **Split:** eight-fold `StratifiedGroupKFold` over groups, strata = collection ×
   label, shuffled; folds 0–1 test, fold 2 validation, the rest train. Try seeds
   42–1041; use the first whose balanced partitions pass the gates. Seed 42 passed.
4. **Balance** 1:1 inside each partition and collection: every minority-label contract
   gets one control of the other label, same Solidity minor version first, then any;
   less-used groups first, then seeded order. Surplus controls are excluded, recorded.
5. **Gates:** ≥ 30 / 5 / 10 distinct groups per label in train / validation / test, and
   both labels of both collections in every partition. Feasibility minimums, not a
   power calculation; never pick seeds after seeing model results.

Result (release `7349c043…`): **train 78/78, validation 17/17, test 30/30** (PRESENT /
ABSENT; aggregated 35/8/14 pairs, RSD 43/9/16 pairs; 231 groups); 119 of 125 pairs
share the Solidity version. Remaining cues to report: RSD is all Solidity 0.8 and short;
aggregated contracts are mostly 0.4; within aggregated, safe contracts come mostly
from the ReentrancyStudy pool and reentrant ones from CGT/ReentrancyStudy positives.
The build is deterministic; `release_manifest.json` hashes every output.

## 7. Teacher

**Locked settings:** Codex CLI **0.156.1** (`codex exec`), model `gpt-6-sol` (GPT-6 Sol),
reasoning effort `medium`, verbosity `low`, ChatGPT-subscription auth, no OpenAI API and
no fallback model. Settings in `configs/teacher.yaml`, prompt in
`configs/prompts/teacher_v2.txt`, answer schema `schemas/teacher_answer.schema.json`;
runner in `src/audit_distill/teacher/`. The core of each call:

```bash
CODEX_HOME=<private home> codex exec -c model="gpt-6-sol" -c model_reasoning_effort="medium" \
  -c model_verbosity="low" <isolation overrides> --ephemeral --sandbox read-only \
  --skip-git-repo-check --ignore-user-config --ignore-rules --json \
  --output-schema schemas/teacher_answer.schema.json --output-last-message <file> --cd <empty dir> -
```

**Isolation:** each run uses a private, empty `CODEX_HOME` holding only a copy of the
ChatGPT login (a refreshed login is copied back), so no global AGENTS.md, skills,
plugins, memories, rules or MCP servers load. Each call runs in a new empty directory
with the task on stdin; shell/exec, apps, plugins, browser, image, memory, sub-agent and
other tool features are disabled, web search is off, and environment, permission and
collaboration instructions are not injected. The environment passed to Codex has no API
key. **Preflight (no model call):** `codex debug prompt-input` renders the exact
model-visible context with sentinel `AGENTS.md` files around the working directory; it
must contain no sentinel and nothing but the task, apart from two fixed Codex
multi-agent notes that no setting removes (recorded in `run.json`). Any tool or
sub-agent event in a call's log, or a file written to its directory, rejects the call.
The CLI version and a ChatGPT login are checked before every run.

**Label-blind generation:** each call shows the teacher exactly one payload (what the
student sees) and the annotation rules — **not the label**. It writes the full report
(analysis, then its own verdict, then the location). A report is accepted only if it is
schema-valid, in bounds, within 480 tokens, used no tools, and its verdict **equals the
benchmark label**. A disagreement is terminal (no retry), is counted per collection and
label, and never changes a label. The teacher may also return UNSUPPORTED with
`INSUFFICIENT_CONTEXT` or `UNRESOLVED_ASSUMPTIONS`. Any rejected train query leaves all
SFT cohorts **together with its matched partner**, keeping them balanced. The accepted
cohort is teacher-agreeable and may be easier; report this selection.

**One query per call and resumability:** concurrency 1; answer schema (strict, key order
is generation order) `{"status": "OK"|"UNSUPPORTED", "report", "reason_code"}`.
Malformed JSON or duplicate keys make an answer invalid. It is checked mechanically
first and label-blind (schema, line bounds, ≤ 480 tokens); only then is its verdict
compared with the label. Only mechanically invalid, missing or tool-rejected output is
retried, once; a call that fails before any answer (network, login) or hits the
subscription limit stops the run without using an attempt. Every call and result is
appended to JSONL immediately; a run directory refuses to resume under different
settings (prompt, schema, model, CLI, isolation, tokenizer, release).

**Records and usage:** `runs/teacher/<run>/` (`pilot`, `train`, `validation`,
`test-ceiling`) holds `run.json` (settings digest, query IDs, preflight, provenance),
append-only `items.jsonl` (per attempt: status accepted/disagreed/unsupported/invalid,
verdict, report, reason, error, tokens), `invocations.jsonl` (query, attempt, prompt
hash, usage, tool items, errors, duration), raw event logs in `events/`, and
`usage.json` (status counts, agreement per collection and label, complete matched
pairs, input/cached/output/reasoning tokens). `--dry-run` makes no model call: it runs
the preflight, writes every prompt to `dry-run/` and reports counts, the invocation
ceiling and token estimates (extrapolated from the pilot once it exists).

**Resource gate:** no teacher call during builds or dry runs. Before the pilot and each
production run, show the exact command and expected usage and wait for approval.
**Pilot:** 3 training queries per label (seed 42, distinct groups, spread over
collections; 6 invocations plus at most 6 retries); inspect every output, then freeze
the prompt (a changed prompt gets a new file name and the pilot is rerun). Generate
training reports only for train and validation; prompt development uses training data
only. **Teacher ceiling:** after the prompt is frozen, run the teacher once, label-blind,
on the test set (60 queries plus retries, separately approved, `--ceiling`); its
verdicts and reports are used only for the ceiling row and the RQ3 test agreement, and
never feed training, prompts or any other decision.

## 8. Report schema

`schemas/audit_report.schema.json`; `src/audit_distill/scoped_reports.py` validates.

```json
{"analysis": "Line 42 sends ether with call.value before line 47 zeroes the balance ...",
 "verdict": "PRESENT",
 "location": {"start_line": 42, "end_line": 47, "function": "withdraw"}}
```

- `analysis` (≤ 1,200 chars): external calls → state updates after them → guards,
  ordering or gas limits → conclusion stating the verdict in the last sentence, citing
  line numbers.
- `verdict`: PRESENT or ABSENT.
- `location`: PRESENT needs `1 ≤ start ≤ end ≤ line count` and a function name or null;
  ABSENT needs null. It is the model's own pointer, not evaluated against gold.
- **Field order is part of the protocol:** `analysis, verdict, location` for the teacher,
  Report-SFT and Base-Report; `verdict, analysis, location` for Report-SFT-VF. Parsing
  requires exactly the condition's order.
- Strict types, all fields required, no extra fields, duplicate keys rejected, no coercion.

## 9. Student and training

**Student:** `Qwen/Qwen3-4B-Instruct-2507` @ `cdbee75f17c01a7cc42f958dc650907174af0554`
(text-only, non-thinking, Apache-2.0, 256K context, standard Qwen3 architecture). Do not
replace it unless unusable (e.g. it cannot train at 8192 tokens on the Colab GPU).

| Weights | Target | Evaluation modes |
| --- | --- | --- |
| Base | none | Base-Label, Base-Report |
| Label-SFT | `PRESENT` or `ABSENT` | verdict |
| Report-SFT | report, analysis first | report |
| Report-SFT-VF | the same reports, verdict first | report (verdict-first order) |
| Multi-SFT (run 2) | each contract twice: label and analysis-first report | verdict (primary), report |

All adapters use the same accepted train IDs, order, seed, epochs and LoRA settings,
with loss on assistant tokens only. System prompts `student_label_v3.txt`,
`student_report_v3.txt` and `student_report_vf_v3.txt`; the user message is the same
rendered payload the teacher saw (`audit_distill/payload.py`); the two report prompts
differ only in the stated field order. `build_student_dataset.py` writes
`data/processed/student/`: `train_<condition>.jsonl` (prompt/completion chat records in
one seeded order), `{validation,test}_<condition>.jsonl` (every query, prompt only),
`shared_cohort.json` and hashed statistics. Built: **140 train examples (70 pairs, 37/58
groups per label)**; 8 teacher disagreements removed with their 8 partners; longest
train sequence 6,130 tokens; completion tokens 490 (Label-SFT) vs 19,123 (each report
condition).

**LoRA (locked, `configs/training.yaml`):** BF16 base model without quantization (H100);
LoRA r 16, alpha 32, dropout 0.05, bias none, targets q/k/v/o/gate/up/down_proj (adapter
weights kept in FP32 by PEFT); lr 2e-4; 6 epochs (run 1: 3); batch 1 × grad-accum 4; weight decay
0.01; warmup 0.05; cosine; max grad norm 1.0; gradient checkpointing; no packing; seed 42;
max length 8192; BF16 autocast; `adamw_torch_fused`. Expected updates
`3 × ceil(N_train / 4)`; log the actual count. No sweeps; a numerical-stability fix must
be minimal and documented.

**Checkpoint selection:** an adapter is saved after each epoch; after training, each
epoch's adapter greedy-decodes **all 34 validation queries** in the condition's format
and the best validation macro-F1 against the benchmark labels wins (verdicts only, so
validation needs no teacher reports; INVALID counts as wrong; ties: earlier epoch — a
validation loss would not be comparable across formats). Validation teacher reports only
add to RQ3. Implementation: `src/audit_distill/training/train.py` (Transformers, TRL
`SFTTrainer` with prompt/completion records and completion-only loss, PEFT;
optional `uv` group `train`, `torch` from the CUDA 12.6 index); shared generation and
scoring in `src/audit_distill/inference.py`. Checked: TRL's tokenization equals the
built sequences for all 420 train records and the loss covers only the assistant answer
and its end token.

**Colab:** `scripts/colab.py` drives `google-colab-cli`: `up` rents an **H100** VM
(`--gpu`; A100/L4 fallbacks), uploads a bundle (tracked files, `.git`, student data; no
raw data) and runs `uv sync --locked --group train`; `train` starts the three conditions
as a detached job on the VM (`colab exec` calls time out); `status` shows progress;
`fetch` downloads `runs/` without per-epoch checkpoints (selected adapters, selection,
validation predictions, `training_run.json` with environment and provenance); `down`
releases the VM. No notebook-only logic. Real GPU jobs need approval.

## 10. Inference and metrics

- Greedy decoding. Verdict output: trim whitespace; exactly `PRESENT`/`ABSENT`, else
  INVALID. Report output: strict JSON + full schema; fences, partial JSON, wrong types,
  out-of-bounds lines or inconsistent ABSENT fields are INVALID. Never repair.
- **Primary score:** binary macro-F1 = (F1_PRESENT + F1_ABSENT) / 2 over the 60 test
  labels; INVALID counts as a false negative of its gold label, never correct. Also
  PRESENT precision/recall, accuracy, counts, invalid rate, 2×3 confusion matrix, and
  macro-F1 over schema-valid outputs only.
- **Baselines** (fit on train only): constant ABSENT, collection majority, Solidity
  version majority, TF-IDF (identifier/operator 1–2-grams) + logistic regression with
  fixed settings.
- **Slices:** collection (aggregated vs RSD), Solidity version, RSD scenario family.
  Results are reported per collection as the main view: RSD (handcrafted minimal pairs,
  unlikely in pretraining) is the hard subset where base models are at chance; the real
  contracts are mostly textbook patterns that even TF-IDF largely solves.
- **Modes on the same test IDs:** Base-Label, Base-Report, Label-SFT, Report-SFT,
  Report-SFT-VF, Multi-SFT (label and report mode), the baselines above and the teacher
  ceiling.
- **Uncertainty:** paired cluster bootstrap over test groups, identical draws for all
  modes, seed 4242, 2,000 valid replicates (≤ 20,000 draws; discard draws missing a
  label). Percentile 95% intervals for scores and for Report-SFT − Label-SFT (RQ1),
  Report-SFT − Report-SFT-VF (order), Report-SFT − Base-Report,
  Label-SFT − Base-Label, Multi-SFT − Label-SFT and Multi-SFT (report) − Report-SFT,
  overall and within each collection. Too few valid draws → report it.
- **Validity:** valid-JSON and full-schema rates over all queries.
- **Grounding and faithfulness (RQ2, automatic):** share of cited line numbers that
  exist and point at non-blank code; share of reports whose last analysis sentence
  states the report's own verdict and not the opposite; location validity (in bounds,
  on code). No line gold exists, so there is no localization accuracy.
- **Agreement (RQ3):** teacher–label agreement on train/validation/test by collection
  and label, with disagreement and UNSUPPORTED counts, next to the v2.3 mixed-source
  result.
- Test data never tunes prompts, preprocessing or training.
- Implementation: `scripts/predict.py` (GPU; `src/audit_distill/evaluation/predict.py`)
  writes raw outputs and strictly parsed verdicts per mode to `runs/eval/test/`;
  `scripts/evaluate.py` (CPU; `score.py`, settings in `configs/evaluation.yaml`) fits the
  baselines on train, adds the teacher ceiling, and writes `results/metrics.json`,
  `results/results.md` and per-mode predictions (committed).

## 11. Human report evaluation (optional)

If time allows: blinded comparison of Base-Report vs Report-SFT on up to 20 test
queries (balanced labels and collections, seed 42). Random A/B order per query, model
key hidden until rating ends; show the input, gold label and both raw outputs. Per
output: **grounding** 0–2 and **consistency** yes/no (the analysis supports the
output's own verdict). One rater (the author); no LLM judge. The automatic RQ2 metrics
do not depend on it.

## 12. Error analysis and paper

- Export deterministic error examples by stratum (false positives/negatives, INVALID,
  ungrounded or self-contradicting analyses); discuss 3–5 in the paper; never retune.
- ACL format, ≤ 8 content pages: introduction (~1), related work (~1), method (~2–2.5),
  results (~1.5–2), discussion (~1), conclusion (~0.5). One pipeline figure. All tables
  from real result files; no placeholder that looks like a result.
- Tables: dataset flow with every exclusion, composition (split × collection ×
  version), results for all modes with intervals and baselines, report validity and
  grounding, teacher agreement (v3.0 vs v2.3), resources (tokens, steps, GPU time).
- **Allowed claims (if supported):** rationale supervision (and its position) changes
  reentrancy verdicts/report behavior on this benchmark; LoRA adapts this model;
  measured teacher–label agreement and its dependence on label conventions. **Never
  claim:** exhaustive detection, ABSENT = secure, teacher text as gold, locally reviewed
  labels, powered small improvements, general vulnerability competence, production
  readiness.
- Limitations: one benchmark and definition; small test set (60, 30 pairs); RSD is
  handcrafted and short; aggregated code is old (mostly 0.4) with origin/label
  correlation; teacher selection; pretraining exposure (the benchmark is public since
  March 2026, after the student's release but before the teacher's); unequal token
  exposure; one model/seed.

## 13. Reproducibility and repository

- Every run records git commit, config/schema versions, the upstream pin, seeds,
  manifest hashes, teacher/student/prompt/tokenizer versions, `uv.lock`, hardware/CUDA,
  input and output hashes, and actual usage/steps. Content hashes exclude timestamps;
  rebuilds from the same inputs reproduce them.
- Outputs: `data/processed/release/`, `runs/teacher/`, `runs/<condition>/`, `runs/eval/`.
  Raw data, processed data, weights, checkpoints and secrets are gitignored; small
  manifests (`data/manifests/`), configs, prompts, schemas, metrics and paper source
  are committed.
- Code: typed modules under `src/audit_distill/` (`data/`, `teacher/`, later
  `training/`, `evaluation/`), thin scripts, YAML configs, `uv`, Python 3.12, standard
  logging with progress bars. No database, service or framework layers.
- Secrets: Codex uses the user's ChatGPT login; no `OPENAI_API_KEY`. Any `HF_TOKEN`
  stays local. Fail clearly if `codex` is missing or logged out.

```bash
uv run python scripts/fetch_data.py
HF_HUB_OFFLINE=1 uv run python scripts/build_dataset.py
uv run python scripts/generate_teacher.py --split train --pilot --dry-run  # no model call
uv run python scripts/generate_teacher.py --split train --pilot        # after approval
uv run python scripts/generate_teacher.py --split {train,validation}   # after approval
uv run python scripts/generate_teacher.py --split test --ceiling       # after approval
HF_HUB_OFFLINE=1 uv run python scripts/build_student_dataset.py
uv sync --group train && CUDA_VISIBLE_DEVICES= uv run python scripts/train.py --condition report --smoke
uv run python scripts/colab.py up && uv run python scripts/colab.py train   # H100, after approval
uv run python scripts/colab.py predict      # test predictions for all modes on the VM
uv run python scripts/colab.py status | fetch | down
uv run python scripts/evaluate.py           # baselines, ceiling, metrics -> results/
# planned
uv run python scripts/make_paper_assets.py
```

## 14. Phases

1. Foundation · 2. Dataset **(done, v3.0)** · 3. Teacher (approved pilot, approved
production, approved test ceiling) · 4. Student formatting (`shared_cohort.json`:
identical accepted train IDs, all three sequences ≤ 8192, gates rechecked) · 5. Training
(three approved Colab jobs) · 6. Evaluation · 7. Optional human rating · 8. Paper.

Do not skip a failed earlier gate. Done means: documented commands reproduce the
experiment, the release is hashed, teacher generation is isolated/resumable/auditable,
all SFT conditions train through the same Colab workflow, all modes are evaluated
deterministically, tables come from real files, and the paper fits eight pages with
only supported claims.

## 15. At a glance

```text
expert-labelled contracts (one definition) -> exclusions -> groups -> grouped split
        -> 1:1 balance per partition and collection
        -> train: label-blind teacher, keep agreeing reports (pairwise)
        -> Label-SFT, Report-SFT, Report-SFT-VF on identical accepted IDs
        -> validation (all 34): checkpoint selection on verdicts
        -> test (60): base modes, four adapters, baselines, teacher ceiling
        -> macro-F1 with group intervals, grounding/faithfulness, agreement
```

## 16. Configuration

`configs/data.yaml` (source pin, tokenizer/budgets, definition and assumptions,
exclusions, grouping, split, balance, gates), `configs/teacher.yaml` (teacher, release
pin, retries, pilot), `configs/student.yaml` (student prompts, generation budgets, train
gate), `configs/training.yaml` (LoRA). Unknown fields and incompatible
versions are rejected; builds and dry runs never start teacher or GPU work.

## 17. Decision log

Decided by the project owner before any training run or model result.

- **2026-09-26 · Follow-up protocol (run 2), declared before running it.** Run 1 (original
  protocol: 3 epochs; results in `results/run1-original/`) found Label-SFT ≥ Report-SFT,
  with the report conditions undertrained by validation and training evidence alone:
  Report-SFT's validation macro-F1 still rising (0.515 → 0.646 → 0.647) and its training
  loss still ≈ 0.55 after 105 steps. Run 2 changes exactly two things for all conditions:
  **6 epochs** (per-epoch validation selection unchanged) and a fourth condition,
  **Multi-SFT** (Hsieh et al. 2023: each contract as a label task and as a report task,
  answered in label mode; also evaluated in report mode). No other hyperparameter is
  tuned: 34 validation contracts cannot support sweeps, and test results were already
  seen. Results are reported per collection (real vs RSD), since base models score well
  only on the textbook-pattern real contracts. Both runs are reported in the paper;
  run 2 writes to `runs/run2-multi/` and `results/run2-multi/`.
- **2026-09-26 · BF16 LoRA instead of QLoRA.** Training runs on a Colab H100, where the
  4B model fits unquantized (~8 GB in BF16); QLoRA was chosen only to fit smaller GPUs.
  Dropping 4-bit quantization removes quantization noise and speeds up training; LoRA
  rank, targets and all hyperparameters are unchanged. The 8-bit paged optimizer is
  replaced by standard fused AdamW, and `bitsandbytes` is no longer a dependency.
- **2026-09-25 · Read-only wording fixed; teacher rerun.** The first v3.0 teacher run
  agreed with 93.7% of train labels (148/158; 138 train examples after pairwise
  removal). Four of its ten train disagreements flagged safe RSD variants only because
  an automatic public getter exposes a stale value during a guarded call; the
  benchmark's read-only scenarios show that only views other code relies on count, so
  assumption 4 was narrowed (training evidence only). Seven were plausible edge-case
  attacks on safe contracts (kept as filtering), one a teacher error (static calls in
  0.4.24). Three validation delegatecall scenarios were answered ABSENT/UNSUPPORTED;
  left unchanged because prompts are developed on training data only (RQ3 finding).
  Query IDs became code identities; the one-time split change this caused is by rule,
  not chosen by results. A contract duplicated across two RSD families now links both
  families (previously one family link could be lost). The first run is kept locally in
  `runs/teacher-v3.0-first/`.
- **2026-09-25 · Switch to one expert-verified benchmark (v3.0).** The v2.3 teacher run
  (GPT-6 Sol, label-blind, 322 calls) agreed with the mixed-source labels only 62%
  (train PRESENT 74%, ABSENT 51%): the sources contradict each other. SCRUBD's own
  comments mark calls to owner-set addresses and `onlyOwner` functions as safe
  (62/101 of its train negatives rejected), while the SmartBugs-wild reviewers mark
  nearly every external call as reentrant, even checks-effects-interactions code (13/20
  positives rejected). Pairwise removal would have left 48 train and 6 validation pairs
  with a contradictory test set. Options weighed: filtering and re-matching
  (contradictory test), consistent-subset evaluation (circular), teacher labels as gold
  (measures imitation), manual adjudication (owner declined), SCRUBD only (≤ 92 pairs,
  student labels, visible errors), ReentrancyStudy (34 positives), ReentrancyBook (22
  positives), DIVE (tool-vote labels). Chosen: the Ca' Foscari benchmarks (Ressi et al.
  2026), which three experts re-labelled under one written definition; the check,
  assumptions and teacher prompt now follow it. Bug-injected contracts are excluded
  (label-revealing artifacts). The task becomes whole-contract; line localization is
  dropped (no line gold); the SmartBugs external view is dropped (different
  convention). Validation checkpoint selection uses all validation queries (verdicts
  only). The v2.3 result is kept in `data/manifests/teacher_v2.3_mixed_sources.json`.
- **2026-09-25 · One query per teacher call** instead of batches of five: the teacher
  sees exactly the student's input, judgments are independent, and a bad answer affects
  only itself.
- **2026-09-25 · Teacher runner.** Codex 0.156.1 cannot hide the filesystem from its
  tools and always loads `$CODEX_HOME/AGENTS.md`, so isolation is a private `CODEX_HOME`,
  disabled tools, an offline `prompt-input` preflight and rejection of any tool event.
  Overlength reports count as mechanically invalid (retried once, label-blind); calls
  that fail before any answer stop the run without using an attempt.
- **2026-09-24 · Leaner report, newer models, NLP framing.** The report is only
  `analysis`, `verdict`, `location`. Teacher GPT-6 Sol (`gpt-6-sol`, medium) with Codex
  CLI 0.156.1. Student Qwen3-4B-Instruct-2507 (the 1.5B coder model would likely fail
  the zero-shot format; Qwen3.5 small models need unreleased `transformers`). RQs
  reframed as rationale distillation, grounding/faithfulness and teacher–label
  agreement, with a one-time teacher ceiling on test and a verdict-first ablation.
- **2026-09-24 · Label-blind teacher.** The teacher judges without the label; only
  agreeing reports train (pairwise removal keeps balance). A label-aware teacher tends
  to rationalize any label.
- **2026-09-23 · Analysis before verdict** so greedy decoding reasons before deciding.
  **Validation macro-F1 checkpoint selection**, since losses are not comparable across
  formats. **Balanced matched cohorts** against surface shortcuts (on the v2.2 pool,
  scope kind + pragma alone reached macro-F1 0.62).
- **2026-09-22 · Reentrancy only**, narrowed from several vulnerability families.
