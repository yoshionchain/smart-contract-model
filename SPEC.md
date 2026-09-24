# Synthetic Audit Distillation — Specification

**Version:** 2.3 (2026-09-24) · **Status:** dataset built; teacher pipeline next ·
**Deadline:** 2026-09-30 23:59 · **Type:** university NLP project, ACL-format paper

This is the project guideline. It may change when a change clearly improves the
project; record every approved change in the decision log (Section 17).

---

## 1. Goal and research questions

Can a small code model learn to judge reentrancy in a given scope of real Solidity
code, and does training it to write a grounded analysis **before** its verdict help?
Code and labels are real and traceable to published human annotations. The teacher
writes explanatory supervision only; it never creates code or changes labels.

- **RQ1:** Does report-supervised fine-tuning (Report-SFT) improve verdicts over the
  unchanged model with the same output format (Base-Report)?
- **RQ2:** Does writing an analysis before the verdict (Report-SFT) beat verdict-only
  fine-tuning (Label-SFT), and how do both compare with simple lexical baselines?
  Completion-token exposure differs between conditions; report it. This is not an
  equal-token ablation.
- **RQ3:** Are generated reports schema-valid, localized to annotated lines, and
  grounded in the code (human-rated)? Agreement with teacher text is not correctness.

Hypotheses (directional; negative or mixed results are valid): H1 Label-SFT > Base-Label;
H2 Report-SFT > Base-Report on verdicts and validity; H3 open: analysis-first may help
by reasoning before deciding or hurt when a flawed analysis propagates; H4 Report-SFT
> Base-Report on human-rated grounding. One seed and limited groups restrict claims
about small differences.

**Out of scope:** other vulnerability classes, generated/injected code, scanner votes
as gold, LLM relabeling of test data, patch-based negatives, RAG, agents, extra
student architectures, hyperparameter sweeps, deployment, BLEU/ROUGE as correctness.

## 2. Terms

- **Query:** one check + one scope (FILE, CONTRACT or FUNCTION) + the full source + assumptions.
- **PRESENT / ABSENT:** the check holds / does not hold for that scope under the stated
  convention. ABSENT never means the code is secure. **UNKNOWN** (missing, disputed or
  unsupported evidence) stays in the evidence ledger and is never a target or a negative.
- **Group:** connected component of known project/deployment/clone links; the unit of
  splitting and uncertainty. Unknown ancestry is not proof of independent projects.
- **Teacher:** GPT-5.6 Sol via Codex CLI. **Student:** Qwen2.5-Coder-1.5B-Instruct.
  **Label-SFT / Report-SFT:** its two adapters. **Base-Label / Base-Report:** the
  unchanged model with the two output prompts.

## 3. The check

| Check | Definition shown to every model |
| --- | --- |
| `REENTRANCY` | SWC-107 reentrancy: does this scope make an external call or ether transfer through which the recipient could re-enter the contract before its state updates are complete? |

Supplied assumption: *"Any address that receives a call or ether may be a contract that
runs arbitrary code."* The definition follows the SWC-107 labelling convention of the
source annotators (e.g. a transfer before a state update counts), not a stricter
exploitability reading (decision log, 2026-09-24).

- Function scope covers execution starting in that function, including called
  helpers/modifiers; file scope covers the whole file. Scope boundaries are not
  vulnerable-line gold.
- Missing imported guards, base contracts or deployment state are never invented.
- Read-only reentrancy, oracle/economic manipulation and cross-protocol behavior are
  out of scope. A `nonReentrant` name is not proof of protection.
- A pragma is a compiler screen, not a deployment date or EVM fork.
- Non-reentrancy findings stay in the ledger and never imply reentrancy ABSENT.

## 4. Sources

| Source | Pinned revision | Role |
| --- | --- | --- |
| [DAppSCAN-source](https://github.com/InPlusLab/DAppSCAN) | `66a56619c44770e05c2db600fa6468115ff0dcd5` | Development: audit-derived positives |
| [SCRUBD-CD](https://github.com/sujeetc/SCRUBD) | `9dba1928d4aea9a5d27014e5f31a8ed0b703f711` | Development: function judgments (CD `labels.csv`; SD excluded) |
| [Salzano et al.](https://github.com/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts) | `da079440bf2cf4fd803c864ef29aeea8a3da50c3` | Development: corrected manual line annotations; its SmartBugs-curated part is external |
| [CGT](https://github.com/gsalzer/cgt) | `f8cd72cf7fbbfebc809c454667eee271706a4b2b` | Inventory/leakage only (labels unverified) |
| [ScBench](https://github.com/blockchain-security-artifacts/sc-developer-study-1) | `840d5fadd392f4777045fa1af3299fd903e9c6bf` | Development: property judgments |
| [SmartBugs Curated](https://github.com/smartbugs/smartbugs-curated) | `230e649123477eff332742a59a1c7cc6dc286cab` | Protected external positives with lines |
| [FORGE-Curated](https://github.com/shenyimings/FORGE-Curated) | `a6b8506343184045074909e6619a67a44da4b1a5` | Inventory/leakage only (modern challenge unavailable) |

- Record original collection ancestry; repackaged copies are not new contracts, and
  headline dataset sizes are never summed as independent evidence.
- **SCRUBD:** blank cells are UNKNOWN; names must resolve to real declarations; keep
  student-review provenance and analyzer selection bias.
- **Salzano:** use the corrected manual labels, never the `zeus_safe`/`zeus_vulnerable`
  collection names as verdicts. Their "no findings" files are reentrancy negatives:
  three validators annotated every instance against all DASP Top-10 categories and
  double-validated every not-vulnerable judgment (arXiv:2505.15756).
- **ScBench:** filenames encode labels and never enter prompts; repeated addresses
  are not independent contracts.
- **CGT:** allowed originals CodeSmells, ContractFuzzer, Doublade, eThor, EthRacer,
  EverEvolvingG, NPChecker, Zeus; SolidiFI, JiuZhou, NotSoSmartC, SWCregistry and
  SBcurated excluded. No documented human protocol, so no CGT label is eligible.
- **FORGE:** tags/keywords are candidate selectors only; a modern challenge would need
  the exact audited pre-fix revision and human verification, so it is not run.
- Fetch only pinned paths, verify checksums/revisions, record license notices, keep raw
  code local (gitignored). Research leads (Reentrancy Redux, "Reentrancy Detection in
  the Age of LLMs", incident/PoC repos) are not admitted data.

## 5. Model input and records

- **Sanitization:** blank all comments in every corpus, preserving length, CR/LF
  positions and quoted literals. Render lines as `0001 | ...`; no phantom final line.
- **Input payload** (identical for every model and condition): `check_id`, definition,
  scope kind and name, assumptions, and the complete numbered source file (never a
  snippet or window). It never contains dataset names, paths, addresses, labels,
  SWC tags, audit text, annotation lines or evidence tiers.
- **Hashes:** `raw_sha256`, `code_sha256` (LF, trimmed trailing whitespace/edge lines),
  `code_identity_sha256` (lexical token spellings), `source_input_sha256` (numbered
  source), `model_input_sha256` (canonical payload). Hashes never rewrite input.
- **Scopes** resolve to unique declarations (contract + full signature, incl.
  constructor/fallback/receive). Overloaded, inherited or ambiguous names are excluded,
  never guessed. Query identity = lexical identity + scope tokens + check + assumptions;
  duplicate support coalesces into one query; distinct scopes in one file are kept and
  always share a group.
- **Budgets** (pinned tokenizer `Qwen/Qwen2.5-Coder-1.5B-Instruct` @
  `2e1fd397ee46e1388853d2af2c993145b0f1098a`, no special tokens): numbered source
  ≤ **6000** tokens (longer sources are excluded and counted, never truncated); full
  chat sequence ≤ **8192** in both conditions; teacher report ≤ **480** tokens as
  canonical JSON (schema order, UTF-8, compact separators); inference allows **512**
  new tokens for reports and **16** for verdicts.
- **Records** are typed (Pydantic), persisted as Parquet/JSONL, never in a database.

## 6. Labels, grouping and the dataset

**Evidence rules**

- A label is eligible only with an upstream assessment backed by a documented human
  protocol (`UPSTREAM_REVIEWED`). Tool-only, LLM-only, synthetic and unverified
  labels never enter training or evaluation. Labels are used as-is; there is no
  local label review, and the paper must say so.
- ABSENT needs an explicit negative for the same check and scope, or documented
  coverage that entails it. Unannotated DAppSCAN files, blank labels, parser
  failures, tool silence and other weaknesses' labels are UNKNOWN, never ABSENT. A
  negative function is never lifted to its contract or file.
- Opposing reentrancy judgments on a compatible scope make the identity UNKNOWN
  (quarantined). No majority votes, no preferring a source.

**Leakage groups** (built over all readable raw corpora before any filtering)

1. Known project/repository/deployment/audit links and same-code aliases (transitive).
2. Exact full-source token skeletons (identifiers alpha-renamed, literals typed,
   pragmas ignored).
3. Exact clones of assessed functions of ≥ 50 tokens.
4. Near-clone sources/contracts of ≥ 100 tokens with length ratio ≥ 0.8 and token
   5-gram Jaccard ≥ 0.85, each edge verified exactly.

Shared libraries that appear in no model context do not merge projects. Any component
touching SmartBugs is external only; FORGE components stay reserved. No source, hash,
query, group or known project crosses partitions.

**Release** (`build_dataset.py --stage release`, settings in `configs/release.yaml`)

1. Eligible pool: 225 PRESENT (157 groups) / 836 ABSENT (653 groups).
2. At most 3 queries per group and label (seeded hash order).
3. Seven-fold `StratifiedGroupKFold` over groups, strata = collection × label, shuffled;
   fold 0 test, fold 1 validation, the rest train. Try seeds 42–1041; use the first
   whose matched partitions pass the gates. Seed 42 passed.
4. Inside each partition, 1:1 matching: every PRESENT query gets one ABSENT control,
   trying keys (collection, scope kind, pragma) → (collection, scope) → (scope, pragma)
   → (scope) → any; unused groups first, then seeded order. Surplus negatives are
   excluded and recorded, never relabeled.
5. Gates: ≥ 30 / 5 / 10 distinct groups per label in train / validation / test, and at
   least one collection with both labels in each partition. These are feasibility
   minimums, not a power calculation; never pick seeds after seeing model results.

Result: 134/134 train, 27/27 validation, 27/27 test, plus 30 SmartBugs external
positives. Each cohort row carries its label, match pair, collection, scope, pragma,
upstream vulnerable lines on the exact file (84 positives), and the exact model input.
`release_manifest.json` hashes everything and pins the inventory fingerprint.
Remaining cues to report: DAppSCAN is positive-only; pragma 0.6/0.7 is almost always
PRESENT; ~72% of code is Solidity 0.4; balanced metrics do not reflect prevalence.

## 7. Teacher

**Locked settings:** Codex CLI **0.154.0** (`codex exec`), model `gpt-5.6` (GPT-5.6 Sol),
reasoning effort `medium`, verbosity `low`, ChatGPT-subscription auth, no OpenAI API and
no fallback model. Equivalent invocation:

```bash
codex exec --model gpt-5.6 -c model_reasoning_effort="medium" -c model_verbosity="low" \
  --ephemeral --sandbox read-only --ask-for-approval never --ignore-user-config \
  --ignore-rules --output-schema <batch-schema.json> --json -o <output.json> -
```

**Isolation:** run in a new empty temp directory with the task on stdin; disable shell/
file tools, web search, MCP, skills, subagents and inherited instructions; restrict the
filesystem view. Before the pilot, a local preflight must show that sentinel files
outside the allowed view are unreadable; if the CLI cannot enforce this, stop and
report. Reject any invocation whose event log shows tool use.

**Label-blind generation:** the teacher receives only opaque IDs, the payload and the
annotation rules — **not the label**. It writes the full report (analysis first, then
its own verdict). A report is accepted only if it is schema-valid, in bounds, within
480 tokens, used no tools, and its verdict **equals the upstream label**. A
disagreement is terminal (no retry), is counted as a label-noise estimate per
collection and label, and never changes a label. The teacher may also return
UNSUPPORTED with `INSUFFICIENT_CONTEXT` or `UNRESOLVED_ASSUMPTIONS`. Any rejected
training/validation query leaves both SFT cohorts **together with its matched
partner**, keeping the cohorts balanced. The accepted cohort is teacher-agreeable and
may be easier; report and discuss this selection.

**Batching and resumability:** up to 5 queries per invocation, concurrency 1, at most 2
attempts (one retry only for mechanically invalid/missing outputs). A transport schema
wraps `{"annotations": [{"sample_id", "status": "OK"|"UNSUPPORTED", "report", "reason_code"}]}`;
every requested ID exactly once. Validate the ID map first, then each report, so one
bad item does not discard the others; malformed JSON or duplicate IDs invalidate the
batch. Queries sharing a source may reference one source table. Cache identity: model
input hash, definition hash, teacher settings, prompt hash, schema hashes, CLI/
isolation version. Persist every valid item immediately; stop cleanly when the
subscription is exhausted.

**Records and usage:** append-only JSONL per item (IDs, input hash, report or reason,
versions, attempts, validation result, timestamps, usage) and
`runs/teacher/<run-id>/usage.json` (CLI version, invocations, retries, accepted/
disagreeing/unsupported/rejected counts, input/cached/output/reasoning tokens; missing
usage is null, not zero). A zero-call dry run shows counts by label/collection, batches,
invocations and token estimates.

**Resource gate:** no teacher call during builds or dry runs. Before the pilot and each
production run, show the exact command and expected usage and wait for approval.
**Pilot:** up to 3 training queries per label (≤ 6, seed 42, distinct groups preferred,
≤ 2 invocations); inspect every output, then freeze prompts in `configs/prompts/`.
Generate only train and validation; never test or external data. Prompt development
uses training data only.

## 8. Report schema

`schemas/audit_report.schema.json`; field order is part of the protocol.

```json
{"analysis": "Line 42 sends ether with call.value before line 47 zeroes the balance ...",
 "verdict": "PRESENT", "severity": "HIGH",
 "location": {"start_line": 42, "end_line": 47, "function": "withdraw"},
 "exploit_scenario": "...", "recommendation": "..."}
```

- `analysis` (≤ 1,200 chars): external calls → state changes around them → guards or
  ordering → conclusion in the last sentence, citing line numbers. ABSENT analyses
  stay within the check and scope.
- `verdict`: PRESENT or ABSENT. `severity`: LOW–CRITICAL for PRESENT, `NONE` for ABSENT.
- `location`: PRESENT needs `1 ≤ start ≤ end ≤ line count` and a function name or null;
  ABSENT needs null. `exploit_scenario`, `recommendation`: ≤ 900 chars for PRESENT,
  null for ABSENT.
- Strict types, all fields required, no extra fields, duplicate keys rejected, no coercion.

## 9. Student and training

**Student:** `Qwen/Qwen2.5-Coder-1.5B-Instruct` @ `2e1fd397ee46e1388853d2af2c993145b0f1098a`
(small, code-tuned, Apache-2.0, fits QLoRA on Colab). Do not replace it unless unusable.

| Weights | Target | Evaluation modes |
| --- | --- | --- |
| Base | none | Base-Label, Base-Report |
| Label-SFT | `PRESENT` or `ABSENT` | verdict |
| Report-SFT | full report (analysis first) | structured report |

Both adapters use the same accepted train/validation IDs, order, seed, epochs and QLoRA
settings, with loss on assistant tokens only. Prompts `student_label_v2.3.txt` and
`student_report_v2.3.txt` share the identical payload; no per-dataset variants.

**QLoRA (locked, `configs/training.yaml`):** 4-bit NF4 with double quantization; LoRA
r 16, alpha 32, dropout 0.05, bias none, targets q/k/v/o/gate/up/down_proj; lr 2e-4;
3 epochs; batch 1 × grad-accum 4; weight decay 0.01; warmup 0.05; cosine; max grad norm
1.0; gradient checkpointing; no packing; seed 42; max length 8192; BF16 if supported,
else FP16; `paged_adamw_8bit`. Expected updates `3 × ceil(N_train / 4)`; log the actual
count. No sweeps; a numerical-stability fix must be minimal and documented.

**Checkpoint selection:** after each epoch, greedy-decode validation; keep the best
validation macro-F1 (INVALID counts as wrong; ties: lower loss, then earlier epoch).

**Colab:** training runs through `google-colab-cli` (`uv tool install google-colab-cli`;
`colab new -s audit-train --gpu L4`; T4 fallback; A100 optional), cloning the repo and
running the same `uv` commands; download adapters, logs, effective config and package
versions with `colab download`. No notebook-only logic. Real GPU jobs need approval.

## 10. Inference and metrics

- Greedy decoding. Verdict output: trim whitespace; exactly `PRESENT`/`ABSENT`, else
  INVALID. Report output: strict JSON + full schema; fences, partial JSON, wrong types,
  out-of-bounds lines or inconsistent ABSENT fields are INVALID. Never repair.
- **Primary score:** binary macro-F1 = (F1_PRESENT + F1_ABSENT) / 2 over gold labels;
  INVALID counts as a false negative of its gold label, never correct. Also report
  PRESENT precision/recall, accuracy, counts, invalid rate, 2×3 confusion matrix, and
  macro-F1 over schema-valid outputs only.
- **Baselines** (fit on train only): constant ABSENT, training majority,
  collection majority, (scope, pragma) majority, TF-IDF (identifier/operator 1–2-grams
  of the scoped code) + logistic regression with fixed settings.
- **Slices:** collection, scope kind, pragma, including within-SCRUBD.
- **Uncertainty:** paired cluster bootstrap over test groups, identical draws for all
  modes, seed 4242, 2,000 valid replicates (≤ 20,000 draws; discard draws missing a
  label). Percentile 95% intervals for scores and for Report-SFT − Base-Report,
  Label-SFT − Base-Label, Report-SFT − Label-SFT. Too few valid draws → report it.
- **Validity:** valid-JSON and full-schema rates over all queries.
- **Localization** (test positives with lines, and SmartBugs): hit = valid PRESENT
  report whose interval contains an annotated line; denominator = all such positives.
  Also span fraction and annotated-line precision over valid in-bounds reports.
  Teacher lines and function bounds are never gold.
- **Cohorts:** test (primary; all four modes on the same IDs) and SmartBugs external
  (positive-only: recall, validity, localization). FORGE: reported as unavailable.
  Test data never tunes prompts, preprocessing or training.

## 11. Human report evaluation

Blinded comparison of Base-Report vs Report-SFT on up to 25 test queries (round-robin
PRESENT then ABSENT, seed 42, distinct groups preferred). Random A/B order per query
(seed 42), model key hidden until rating ends; show the input, gold label and both raw
outputs; keep failures. Ratings 0–2: grounding (all queries); exploit plausibility,
mitigation and severity (gold positives only; a wrong ABSENT scores 0). On negatives
also record false vulnerability or global-security claims. Report per-criterion means,
denominators and paired grounding preference. One rater (the author) is acceptable; no
LLM judge. Optionally spot-check ~10 accepted teacher reports for grounding.

## 12. Error analysis and paper

- Export deterministic error examples by stratum (false positives/negatives, INVALID,
  wrong localization, ungrounded analyses); discuss 3–5 in the paper; never retune.
- ACL format, ≤ 8 content pages: introduction (~1), related work (~1), method (~2–2.5),
  results (~1.5–2), discussion (~1), conclusion (~0.5). One pipeline figure; confusion
  matrices or interval plots only if useful. All tables from real result files; no
  placeholder that looks like a result.
- Tables: dataset flow with every exclusion, composition (split × collection × scope ×
  pragma), results for all modes with intervals and baselines, report validity/
  localization/human ratings, resources (tokens, teacher usage, steps, GPU time).
- **Allowed claims (if supported):** report supervision changes scoped reentrancy
  verdicts/report behavior on this corpus; QLoRA adapts this model; measured transfer to
  SmartBugs. **Never claim:** exhaustive detection, ABSENT = secure, independent projects
  from different addresses, teacher text as gold, locally reviewed labels, powered small
  improvements, general vulnerability competence, modern exploitability, production
  readiness, or reentrancy as the most common current attack.
- Limitations to discuss: unverified labels under a broad convention, teacher selection
  and noise, old-code concentration, DAppSCAN positive-only, incomplete ancestry,
  pretraining exposure, unequal token exposure, one model/seed/rater, small test set.

## 13. Reproducibility and repository

- Every run records git commit, config/schema versions, upstream pins, seeds, manifest
  hashes, teacher/student/prompt/tokenizer versions, `uv.lock`, hardware/CUDA, input and
  output hashes, and actual usage/steps. Deterministic content hashes exclude timestamps;
  rebuilds from the same inputs reproduce them.
- Outputs: `data/processed/inventory/`, `data/processed/release/`, `runs/teacher/`,
  `runs/label-sft/`, `runs/report-sft/`, `runs/eval/`. Raw data, processed data, weights,
  checkpoints and secrets are gitignored; small manifests (`data/manifests/`), configs,
  prompts, schemas, metrics and paper source are committed.
- Code: typed modules under `src/audit_distill/` (`data/`, later `teacher/`,
  `training/`, `evaluation/`), thin scripts, YAML configs, `uv`, Python 3.12, standard
  logging with progress bars. No database, service or framework layers.
- Secrets: Codex uses the user's ChatGPT login; no `OPENAI_API_KEY`. Any `HF_TOKEN`
  stays local. Fail clearly if `codex` is missing or logged out.

```bash
uv run python scripts/fetch_data.py
uv run python scripts/build_dataset.py --stage inventory
uv run python scripts/validate_dataset.py
uv run python scripts/build_dataset.py --stage release
# planned
uv run python scripts/generate_teacher.py --split train --pilot --dry-run
uv run python scripts/generate_teacher.py --split train --pilot        # after approval
uv run python scripts/generate_teacher.py --split {train,validation}   # after approval
uv run python scripts/build_student_dataset.py
uv run python scripts/train.py --condition {label,report}              # Colab, after approval
uv run python scripts/evaluate.py
uv run python scripts/build_human_eval.py && uv run python scripts/score_human_eval.py
uv run python scripts/make_paper_assets.py
```

## 14. Phases

1. Foundation · 2. Dataset **(done)** · 3. Teacher (mocks + dry run, approved pilot,
approved production) · 4. Student formatting (`shared_cohort.json`: identical accepted
IDs, both sequences ≤ 8192, gates rechecked) · 5. Training (approved Colab jobs) ·
6. Evaluation · 7. Human report evaluation · 8. Paper and reproducibility.

Do not skip a failed earlier gate. Done means: documented commands reproduce the
experiment, the release is hashed, teacher generation is isolated/resumable/auditable,
both SFT conditions train through the same Colab workflow, all four modes are evaluated
deterministically, human ratings are blinded, tables come from real files, and the paper
fits eight pages with only supported claims.

## 15. At a glance

```text
real source + upstream human labels (SWC-107 convention)
        -> leakage groups -> eligibility -> grouped split -> 1:1 matched cohorts
        -> train/validation: label-blind teacher, keep agreeing reports (pairwise)
        -> Label-SFT and Report-SFT on identical accepted IDs
        -> test: Base-Label, Base-Report, Label-SFT, Report-SFT + baselines
        -> macro-F1 with group intervals, validity, localization, blinded human rating
```

## 16. Configuration

`configs/project.yaml` (pins, paths, tokenizer/budgets, grouping thresholds),
`configs/taxonomy.yaml` (check definition and candidate mappings: SWC-107, `RE`,
`reentrancy`; no-finding negatives need confirmed coverage), `configs/release.yaml`
(eligibility, cap, matching, split, gates), `configs/training.yaml` (QLoRA). Unknown
fields and incompatible versions are rejected; builds and dry runs never start teacher
or GPU work.

## 17. Decision log

Decided by the project owner before any teacher call, training run or model result.

- **2026-09-24 · Label-blind teacher.** The teacher judges without the label; only
  agreeing reports train (pairwise removal keeps balance). A label-aware teacher tends to
  rationalize any label, so its UNSUPPORTED rate would understate label noise.
- **2026-09-24 · Upstream labels, SWC-107 convention, no local review.** An assistant spot
  check of 18 labels (not human validation) found 9 clearly consistent, 2 plausible under
  callback assumptions and 7 inconsistent with the stricter earlier definition
  ("re-entry that violates accounting invariants", trusted owners), e.g.
  `owner.transfer(this.balance)`, 2300-gas `send` loops and calls to fixed trusted
  contracts labelled PRESENT, and one refund-before-update labelled ABSENT. The definition
  now states the sources' convention; the review queues, review tool and freeze stage
  were removed. The whole matched held-out fold is the test set.
- **2026-09-23 · Analysis before verdict** so greedy decoding reasons before deciding
  (RQ2). **Validation macro-F1 checkpoint selection**, since losses are not comparable
  across formats.
- **2026-09-23 · Balanced matched cohorts.** On the imbalanced pool, scope kind + pragma
  alone reached macro-F1 0.62 in grouped CV (constant ABSENT 0.44); on the matched pool
  0.50. TF-IDF still reached ~0.73, hence the lexical baseline. The unmatched negatives
  are 88% file scope and 95% Solidity 0.4, so keeping them would reintroduce the shortcut.
  Group cap (two DAppSCAN projects had 13 positives each) and split-then-match (matching
  first chained groups into blocks of up to 82 queries).
- **2026-09-23 · CGT and FORGE inactive; Salzano coverage confirmed** from its paper.
- **2026-09-22 · Reentrancy only**, narrowed from several vulnerability families to focus
  the NLP comparison. OWASP data does not support calling reentrancy the most common
  current attack. Recent reentrancy benchmarks share CGT ancestry or contain handcrafted
  code and are related work only.
