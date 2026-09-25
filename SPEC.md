# Synthetic Audit Distillation — Specification

**Version:** 2.3 (2026-09-24) · **Status:** dataset built; teacher pipeline next ·
**Deadline:** 2026-09-30 23:59 · **Type:** university NLP project, ACL-format paper

This is the project guideline. It may change when a change clearly improves the
project; record every approved change in the decision log (Section 17).

---

## 1. Goal and research questions

This is **rationale distillation** for a code-understanding task: does training a
small language model on a large model's natural-language explanations help it judge
reentrancy in a given scope of real Solidity code, and are its own explanations
grounded? Code and labels are real and traceable to published human annotations. The
teacher writes explanations only; it never creates code or changes labels. Related
work: Distilling Step-by-Step (Hsieh et al. 2023), Ho et al. 2023, Magister et al.
2023, e-SNLI (Camburu et al. 2018), explanation faithfulness (Jacovi & Goldberg 2020;
Wiegreffe & Marasović 2021).

- **RQ1 (main) — Do rationales help?** Does fine-tuning on teacher analyses followed by
  the verdict (Report-SFT) improve verdicts over fine-tuning on labels alone
  (Label-SFT)? Floors: the base model and lexical baselines; ceiling: the teacher.
  **Order ablation:** the same reports with the verdict first (Report-SFT-VF) separate
  "reasoning before deciding" from "extra training signal".
- **RQ2 — Are the student's rationales grounded and faithful?** Do cited line numbers
  exist and hit annotated vulnerable lines, does the location hit them, and does the
  analysis support the model's own verdict (automatic metrics + blinded human rating)?
  Agreement with teacher text is not correctness.
- **RQ3 — Do the LLM and the human annotators agree?** How often does the label-blind
  teacher agree with the upstream SWC-107 labels on train/validation, per collection
  and label, and what kinds of cases does it reject?

Hypotheses (directional; negative or mixed results are valid): H1 all SFT conditions
beat their base-model format; H2 Report-SFT ≥ Label-SFT; H3 open: analysis-first may
beat verdict-first by reasoning before deciding, or lose when a flawed analysis
propagates; H4 Report-SFT analyses are better grounded than Base-Report analyses.
Completion-token exposure differs between Label-SFT and the report conditions (not
between the two report orders); report it. One seed and limited groups restrict
claims about small differences.

**Out of scope:** other vulnerability classes, generated/injected code, scanner votes
as gold, LLM relabeling of any data, patch-based negatives, RAG, agents, extra student
architectures, hyperparameter sweeps, deployment, BLEU/ROUGE as correctness.

## 2. Terms

- **Query:** one check + one scope (FILE, CONTRACT or FUNCTION) + the full source + assumptions.
- **PRESENT / ABSENT:** the check holds / does not hold for that scope under the stated
  convention. ABSENT never means the code is secure. **UNKNOWN** (missing, disputed or
  unsupported evidence) stays in the evidence ledger and is never a target or a negative.
- **Group:** connected component of known project/deployment/clone links; the unit of
  splitting and uncertainty. Unknown ancestry is not proof of independent projects.
- **Teacher:** GPT-6 Sol via Codex CLI. **Student:** Qwen3-4B-Instruct-2507.
  **Label-SFT / Report-SFT / Report-SFT-VF:** its three adapters (verdict only;
  analysis-first report; the same reports verdict-first). **Base-Label / Base-Report:**
  the unchanged model with the verdict and report prompts.

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
- **Budgets** (pinned tokenizer `Qwen/Qwen3-4B-Instruct-2507` @
  `cdbee75f17c01a7cc42f958dc650907174af0554`, no special tokens): numbered source
  ≤ **6000** tokens (longer sources are excluded and counted, never truncated); full
  chat sequence ≤ **8192** in both conditions; teacher report ≤ **480** tokens as
  canonical JSON (UTF-8, compact separators); inference allows **512** new tokens for
  reports and **16** for verdicts.
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

**Locked settings:** Codex CLI **0.156.1** (`codex exec`), model `gpt-6-sol` (GPT-6 Sol),
reasoning effort `medium`, verbosity `low`, ChatGPT-subscription auth, no OpenAI API and
no fallback model. Settings in `configs/teacher.yaml`, prompt in
`configs/prompts/teacher_v1.txt`, answer schema `schemas/teacher_answer.schema.json`;
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
other tool features are disabled, web search is off, and environment, permission,
collaboration and skill instructions are not injected. The environment passed to Codex
has no API key. **Preflight (no model call):** `codex debug prompt-input` renders the
exact model-visible context with sentinel `AGENTS.md` files around the working directory;
it must contain no sentinel and nothing but the task, apart from two fixed Codex
multi-agent notes that no setting removes (recorded in `run.json`). Any tool or
sub-agent event in a call's log, or a file written to its directory, rejects the call.
The CLI version and a ChatGPT login are checked before every run.

**Label-blind generation:** each call shows the teacher exactly one payload (what the
student sees) and the annotation rules — **not the label**. It writes the full report (analysis, then its own
verdict, then the location). A report is accepted only if it is schema-valid, in bounds, within
480 tokens, used no tools, and its verdict **equals the upstream label**. A
disagreement is terminal (no retry), is counted as a label-noise estimate per
collection and label, and never changes a label. The teacher may also return
UNSUPPORTED with `INSUFFICIENT_CONTEXT` or `UNRESOLVED_ASSUMPTIONS`. Any rejected
training/validation query leaves all SFT cohorts **together with its matched
partner**, keeping the cohorts balanced. The accepted cohort is teacher-agreeable and
may be easier; report and discuss this selection.

**One query per call and resumability:** one query per invocation, concurrency 1, so
every judgment is independent and made from the student's own view. The answer schema
(strict: every key required, no extras; key order is generation order) is
`{"status": "OK"|"UNSUPPORTED", "report", "reason_code"}`. Malformed JSON or duplicate
keys make the answer invalid. It is checked mechanically first and label-blind (schema,
line bounds, ≤ 480 tokens); only then is its verdict compared with the label. Only
mechanically invalid, missing or tool-rejected output is retried, once; a call that
fails before any answer (network, login) or hits the subscription limit stops the run
without using an attempt. Every call and result is appended to JSONL immediately; a run
directory refuses to resume under different settings (prompt, schema, model, CLI,
isolation, tokenizer, release).

**Records and usage:** `runs/teacher/<run>/` (`pilot`, `train`, `validation`,
`test-ceiling`) holds `run.json` (settings and their digest, query IDs, preflight,
provenance), append-only `items.jsonl` (per attempt: IDs, label, input hash, status
accepted/disagreed/unsupported/invalid, verdict, report, reason, error, tokens),
`invocations.jsonl` (query, attempt, prompt hash, usage, tool items, errors, duration),
raw event logs in `events/`, and `usage.json` (status counts, agreement per collection
and label, complete matched pairs, input/cached/output/reasoning tokens; calls without
usage are counted, not zeroed). `--dry-run` makes no model call: it runs the preflight,
writes every prompt to `dry-run/` and reports counts, the invocation
ceiling and token estimates (extrapolated from the pilot once it exists).

**Resource gate:** no teacher call during builds or dry runs. Before the pilot and each
production run, show the exact command and expected usage and wait for approval.
**Pilot:** 3 training queries per label (seed 42, distinct groups, spread over
collections; 6 invocations plus at most 6 retries); inspect every output, then
freeze the prompt (a changed prompt gets a new file name, `teacher_v2.txt`, and the pilot
is rerun). Generate training reports only for train and validation. Prompt development
uses training data only. **Teacher ceiling:** after the prompt is frozen, run the teacher
once, label-blind, on the test set (54 queries, 54 invocations plus retries, separately
approved, `--ceiling`); its verdicts and reports are used only for the ceiling row and
never feed training, prompts or any other decision.

## 8. Report schema

`schemas/audit_report.schema.json`; `src/audit_distill/scoped_reports.py` validates.

```json
{"analysis": "Line 42 sends ether with call.value before line 47 zeroes the balance ...",
 "verdict": "PRESENT",
 "location": {"start_line": 42, "end_line": 47, "function": "withdraw"}}
```

- `analysis` (≤ 1,200 chars): external calls → state changes around them → guards or
  ordering → conclusion in the last sentence, citing line numbers. ABSENT analyses
  stay within the check and scope.
- `verdict`: PRESENT or ABSENT.
- `location`: PRESENT needs `1 ≤ start ≤ end ≤ line count` and a function name or null;
  ABSENT needs null.
- **Field order is part of the protocol:** `analysis, verdict, location` for the teacher,
  Report-SFT and Base-Report; `verdict, analysis, location` for Report-SFT-VF. Parsing
  requires exactly the condition's order.
- Strict types, all fields required, no extra fields, duplicate keys rejected, no coercion.

## 9. Student and training

**Student:** `Qwen/Qwen3-4B-Instruct-2507` @ `cdbee75f17c01a7cc42f958dc650907174af0554`
(text-only, non-thinking, Apache-2.0, 256K context, standard Qwen3 architecture; small
next to the teacher but able to write a coherent analysis). Do not replace it unless
unusable (e.g. it cannot train at 8192 tokens on the Colab GPU).

| Weights | Target | Evaluation modes |
| --- | --- | --- |
| Base | none | Base-Label, Base-Report |
| Label-SFT | `PRESENT` or `ABSENT` | verdict |
| Report-SFT | report, analysis first | report |
| Report-SFT-VF | the same reports, verdict first | report (verdict-first order) |

All adapters use the same accepted train/validation IDs, order, seed, epochs and QLoRA
settings, with loss on assistant tokens only. Prompts `student_label_v2.3.txt`,
`student_report_v2.3.txt` and `student_report_vf_v2.3.txt` share the identical payload;
the two report prompts differ only in the stated field order.

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
- **Modes on the same test IDs:** Base-Label, Base-Report, Label-SFT, Report-SFT,
  Report-SFT-VF, the baselines above and the teacher ceiling.
- **Uncertainty:** paired cluster bootstrap over test groups, identical draws for all
  modes, seed 4242, 2,000 valid replicates (≤ 20,000 draws; discard draws missing a
  label). Percentile 95% intervals for scores and for Report-SFT − Label-SFT (RQ1),
  Report-SFT − Report-SFT-VF (order), Report-SFT − Base-Report and
  Label-SFT − Base-Label. Too few valid draws → report it.
- **Validity:** valid-JSON and full-schema rates over all queries.
- **Grounding (RQ2, automatic):** share of line numbers cited in analyses that exist;
  share of annotated positives whose analysis cites an annotated line.
- **Localization** (test positives with lines, and SmartBugs): hit = valid PRESENT
  report whose interval contains an annotated line; denominator = all such positives.
  Also span fraction and annotated-line precision over valid in-bounds reports.
  Teacher lines and function bounds are never gold.
- **Agreement (RQ3):** teacher–label agreement on train/validation by collection and
  label, with the disagreement and UNSUPPORTED counts.
- **Cohorts:** test (primary) and SmartBugs external (positive-only: recall, validity,
  localization). FORGE: reported as unavailable. Test data never tunes prompts,
  preprocessing or training.

## 11. Human report evaluation

Blinded comparison of Base-Report vs Report-SFT on up to 25 test queries (round-robin
PRESENT then ABSENT, seed 42, distinct groups preferred). Random A/B order per query
(seed 42), model key hidden until rating ends; show the input, gold label and both raw
outputs; keep failures. Per output: **grounding** 0–2 (0 contradicted/generic/missing,
1 partly grounded, 2 technically grounded in this code and scope) and **consistency**
yes/no (the analysis supports the output's own verdict); on gold negatives also record
false vulnerability or global-security claims. Report per-criterion means, denominators
and paired grounding preference. One rater (the author) is acceptable; no LLM judge.
Optionally spot-check ~10 accepted teacher reports for grounding.

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
- **Allowed claims (if supported):** rationale supervision (and its position) changes
  scoped reentrancy verdicts/report behavior on this corpus; QLoRA adapts this model;
  measured teacher–annotator agreement; measured transfer to SmartBugs. **Never claim:** exhaustive detection, ABSENT = secure, independent projects
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
- Code: typed modules under `src/audit_distill/` (`data/`, `teacher/`, later
  `training/`, `evaluation/`), thin scripts, YAML configs, `uv`, Python 3.12, standard
  logging with progress bars. No database, service or framework layers.
- Secrets: Codex uses the user's ChatGPT login; no `OPENAI_API_KEY`. Any `HF_TOKEN`
  stays local. Fail clearly if `codex` is missing or logged out.

```bash
uv run python scripts/fetch_data.py
uv run python scripts/build_dataset.py --stage inventory
uv run python scripts/validate_dataset.py
uv run python scripts/build_dataset.py --stage release
uv run python scripts/generate_teacher.py --split train --pilot --dry-run  # no model call
uv run python scripts/generate_teacher.py --split train --pilot        # after approval
uv run python scripts/generate_teacher.py --split {train,validation}   # after approval
uv run python scripts/generate_teacher.py --split test --ceiling       # after approval
# planned
uv run python scripts/build_student_dataset.py
uv run python scripts/train.py --condition {label,report,report-vf}    # Colab, after approval
uv run python scripts/evaluate.py
uv run python scripts/build_human_eval.py && uv run python scripts/score_human_eval.py
uv run python scripts/make_paper_assets.py
```

## 14. Phases

1. Foundation · 2. Dataset **(done)** · 3. Teacher (mocks + dry run, approved pilot,
approved production, approved test ceiling) · 4. Student formatting
(`shared_cohort.json`: identical accepted IDs, all three sequences ≤ 8192, gates
rechecked) · 5. Training (three approved Colab jobs) · 6. Evaluation · 7. Human report
evaluation · 8. Paper and reproducibility.

Do not skip a failed earlier gate. Done means: documented commands reproduce the
experiment, the release is hashed, teacher generation is isolated/resumable/auditable,
all SFT conditions train through the same Colab workflow, all modes are evaluated
deterministically, human ratings are blinded, tables come from real files, and the paper
fits eight pages with only supported claims.

## 15. At a glance

```text
real source + upstream human labels (SWC-107 convention)
        -> leakage groups -> eligibility -> grouped split -> 1:1 matched cohorts
        -> train/validation: label-blind teacher, keep agreeing reports (pairwise)
        -> Label-SFT, Report-SFT, Report-SFT-VF on identical accepted IDs
        -> test: base modes, three adapters, baselines, teacher ceiling
        -> macro-F1 with group intervals, grounding, localization, agreement, human rating
```

## 16. Configuration

`configs/project.yaml` (pins, paths, tokenizer/budgets, grouping thresholds),
`configs/taxonomy.yaml` (check definition and candidate mappings: SWC-107, `RE`,
`reentrancy`; no-finding negatives need confirmed coverage), `configs/release.yaml`
(eligibility, cap, matching, split, gates), `configs/teacher.yaml` (teacher, retries,
pilot), `configs/training.yaml` (QLoRA). Unknown
fields and incompatible versions are rejected; builds and dry runs never start teacher
or GPU work.

## 17. Decision log

Decided by the project owner before any teacher call, training run or model result.

- **2026-09-25 · One query per teacher call** instead of batches of five: the teacher
  sees exactly the student's input, judgments are independent (no anchoring or
  cross-references between examples), and a bad answer affects only itself. Batching
  would have saved little: 245 of 268 training queries have distinct sources.
- **2026-09-25 · Teacher runner.** Codex 0.156.1 cannot hide the filesystem from its
  tools and always loads `$CODEX_HOME/AGENTS.md`, so isolation is a private `CODEX_HOME`,
  disabled tools, an offline `prompt-input` preflight and rejection of any tool event,
  instead of an unreadable-sentinel test. Overlength reports count as mechanically
  invalid (retried once, label-blind); calls that fail before any answer stop the run
  without using an attempt.
- **2026-09-24 · Leaner report, newer models, NLP framing.** The report is only
  `analysis`, `verdict`, `location`: severity, exploit scenario and recommendation were
  subjective, unevaluated, came after the verdict and widened the token gap. Teacher is
  now GPT-6 Sol (`gpt-6-sol`, medium; released September 2026, about half the price of
  GPT-5.6 Sol) with the installed Codex CLI 0.156.1. Student is Qwen3-4B-Instruct-2507:
  the 1.5B coder model would likely fail the zero-shot format and be too weak to benefit
  from reasoning; Qwen3.5 small models were rejected as multimodal with a new
  architecture needing unreleased `transformers`. The RQs are reframed as rationale
  distillation, grounding/faithfulness and teacher–annotator agreement, with a
  one-time teacher ceiling on test and a verdict-first order ablation (third adapter,
  no extra teacher calls).

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
