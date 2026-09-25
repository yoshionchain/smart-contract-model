# Remaining work

Work down this list. [SPEC.md](SPEC.md) is the detailed guideline; its decision log records why things are the way they are. Commands described as *planned* are not implemented yet. Deadline: September 30, 2026, 23:59.

## 1. Dataset (done)

- [x] Fetch the seven pinned sources and build the candidate inventory with leakage groups and mechanical validation.
- [x] Build the final release: upstream-reviewed labels under the SWC-107 convention, group cap, grouped split, 1:1 matched balancing. 134/134 train, 27/27 validation, 27/27 test, 30 SmartBugs external positives. See the README's dataset section.

## 2. Generate and audit teacher supervision (Phase 3)

- [x] **Implemented and checked with mocks:** label-blind prompt (`configs/prompts/teacher_v1.txt`), isolated Codex runner (private `CODEX_HOME`, all tools off, offline `prompt-input` preflight, tool events reject a call), strict answer schema, one query per call, one retry for mechanically invalid output only, pairwise acceptance data, resumable JSONL records, usage log, zero-call dry run. Mock checks covered malformed answers, duplicate keys, extra fields, timeouts, disagreements, UNSUPPORTED, out-of-bounds and over-budget reports, tool use, limits, no-answer failures, stale run directories, the invocation cap and the test guard. The exec command was parse-checked with no login (401, nothing billed).
- [ ] **Approval required for the real pilot:** `uv run python scripts/generate_teacher.py --split train --pilot --max-invocations 12` — 6 training queries (3 per label, dry run lists them), 6 calls plus at most 6 retries. Inspect every output, then freeze the prompt using training data only (a changed prompt gets a new file and the pilot is rerun).
- [ ] **Approval required for each production run:** show the exact train/validation commands and dry-run usage estimate, then wait for approval. Generate only train/validation; preserve valid partial work; report agreement/disagreement rates per collection and label (the label-noise estimate); no test or external data in production runs.
- [ ] **Approval required for the teacher ceiling:** after the prompt is frozen, run the teacher once, label-blind, on the 54 test queries (54 calls plus retries). Its outputs are only the ceiling row.
- [ ] **Optional (~10 reports):** spot-check accepted teacher reports for grounding and correct lines, without removing reports from the cohort.

## 3. Build the matched student dataset (Phase 4)

- [ ] **Implement:** canonical chat formatting and assistant-only loss for Label-SFT, Report-SFT (analysis first) and Report-SFT-VF (same reports, verdict first). Enforce the 6,000-token source budget, 480-token report target, and 8,192-token complete-sequence limit with the pinned tokenizer/template; exclude rather than truncate overlength examples.
- [ ] **Freeze:** identical sorted accepted train/validation IDs for all three conditions in `shared_cohort.json`; reject unsupported/invalid/overlength items (with their matched partners) from all. Recheck train/validation polarity-group and source-breadth gates and report acceptance bias. Stop if a gate fails.

## 4. Train the student conditions (Phase 5)

- [ ] **Implement and smoke-test:** normal Python QLoRA modules and a documented Google Colab CLI workflow using the exact model, adapters, hyperparameters and seeds in SPEC, with per-epoch greedy validation macro-F1 checkpoint selection. Save effective configs, tokenizer/prompt hashes, logs, and adapters.
- [ ] **Approval required for real Colab jobs:** show the exact commands, runtime/resources, dataset and cohort hashes, and expected outputs. Run the three SFT conditions only after explicit approval; check first that Qwen3-4B trains at 8,192 tokens on the chosen GPU. Keep Base as the unchanged model.

## 5. Evaluate without tuning on held-out data (Phase 6)

- [ ] **Implement and run:** the (scope, pragma) majority and TF-IDF logistic-regression baselines fitted on train only, plus the collection-majority baseline.
- [ ] **Implement and run:** deterministic Base-Label, Base-Report, Label-SFT, Report-SFT and Report-SFT-VF inference on the same test IDs, next to the baselines and the teacher ceiling. Report binary PRESENT/ABSENT macro-F1, positive precision/recall, invalid-output/schema rates, paired group-bootstrap uncertainty (Report-SFT − Label-SFT, Report-SFT − Report-SFT-VF, each − its base format), cited-line grounding, teacher–label agreement per collection, and raw predictions. Invalid outputs count as misses under SPEC rules.
- [ ] **Implement and run:** the SmartBugs external view separately. Score localization only against upstream line annotations on the exact file (13 test and 30 SmartBugs positives), never teacher lines or function bounds as gold. Export denominator-aware metrics and error strata; do not retune from test results.

## 6. Human report comparison (Phase 7)

- [ ] **Implement:** select up to 25 test queries and produce randomized, blinded paired Base-Report/Report-SFT cards with a hidden key and the SPEC rubric (grounding 0–2, consistency with own verdict).
- [ ] **Human reviewer:** rate the blinded cards before unblinding. Then score with actual ratings, denominators, paired comparisons, and any documented second-rater agreement.

## 7. Paper and reproducibility (Phase 8)

- [ ] Generate only real dataset, resource, metric, uncertainty, and human-rating tables/figures. Write the ACL paper within the SPEC page limit, frame it as rationale distillation; explain scoped ABSENT, unverified upstream labels under the SWC-107 convention, source concentration, compiler-era limits, incomplete ancestry, teacher noise, and public-pretraining exposure.
- [ ] Bring README commands and outputs into sync with the finished CLI. Verify a fresh `uv sync --locked`, Ruff, deterministic build and artifact-hash checks, and documented end-to-end reproduction. Do not present missing runs as results.

**Immediate next step:** approve and run the teacher pilot (6 training queries, ≤ 12 Codex calls), then inspect the reports.
