# Remaining work

Work down this list. [SPEC.md](SPEC.md) is the detailed guideline; its decision log records why things are the way they are. Commands described as *planned* are not implemented yet. Deadline: September 30, 2026, 23:59.

## 1. Dataset (done, v3.0)

- [x] Switch to the expert-verified Ca' Foscari benchmarks (one definition): exclude bug-injected and overlength contracts, de-duplicate, group clones and RSD scenario families, grouped split, 1:1 balance per partition and collection. 79/79 train, 16/16 validation, 30/30 test; reproducible (`data/manifests/`).
- [x] Keep the v2.3 mixed-source teacher result for the paper (`data/manifests/teacher_v2.3_mixed_sources.json`: 62% agreement; SCRUBD and SmartBugs-wild conventions conflict).

## 2. Teacher supervision

- [x] Runner implemented and checked with mocks, dry runs and a real v2.3 pilot and production run (isolation, retries, resumability and usage logging work; 322/322 calls valid).
- [ ] **Approval required for the v3.0 pilot:** `uv run python scripts/generate_teacher.py --split train --pilot --max-invocations 12` — 6 training contracts (3 per label, both collections), prompt `teacher_v2.txt`. Inspect every output; revise the prompt only for format or grounding problems, using training data only, then freeze it.
- [ ] **Approval required for production:** train (158 calls) and validation (32 calls). Report agreement per collection and label; pairwise removal on train.
- [ ] **Approval required for the teacher ceiling:** after freezing, run once, label-blind, on the 60 test contracts (`--ceiling`). Outputs only feed the ceiling row and RQ3 test agreement.

## 3. Build the matched student dataset (Phase 4)

- [ ] **Implement:** canonical chat formatting and assistant-only loss for Label-SFT, Report-SFT (analysis first) and Report-SFT-VF (same reports, verdict first). Enforce the 6,000-token source budget, 480-token report target and 8,192-token sequence limit with the pinned tokenizer/template; exclude rather than truncate.
- [ ] **Freeze:** identical sorted accepted train IDs for all three conditions in `shared_cohort.json` (rejected queries leave with their matched partner). Recheck the train group gate and report acceptance bias. Validation keeps all 32 queries for checkpoint selection.

## 4. Train the student conditions (Phase 5)

- [ ] **Implement and smoke-test:** Python QLoRA modules and a documented Google Colab CLI workflow with the exact model, hyperparameters and seed in SPEC, with per-epoch greedy validation macro-F1 checkpoint selection. Save effective configs, tokenizer/prompt hashes, logs and adapters.
- [ ] **Approval required for real Colab jobs:** show commands, runtime/resources, dataset and cohort hashes; check first that Qwen3-4B trains at 8,192 tokens on the chosen GPU. Then run the three SFT conditions. Keep Base as the unchanged model.

## 5. Evaluate without tuning on held-out data (Phase 6)

- [ ] **Implement and run:** baselines fitted on train only (constant, collection majority, Solidity-version majority, TF-IDF logistic regression).
- [ ] **Implement and run:** deterministic Base-Label, Base-Report, Label-SFT, Report-SFT and Report-SFT-VF inference on the 60 test contracts, next to the baselines and the teacher ceiling. Macro-F1, PRESENT precision/recall, invalid rates, paired group-bootstrap intervals (Report-SFT − Label-SFT, Report-SFT − Report-SFT-VF, each − its base format), slices by collection and version, grounding/faithfulness (cited lines exist and are code; the conclusion states the report's own verdict), teacher–label agreement, raw predictions.

## 6. Optional human rating (Phase 7)

- [ ] Only if time allows: blinded Base-Report vs Report-SFT cards on up to 20 test contracts, rated for grounding and consistency.

## 7. Paper and reproducibility (Phase 8)

- [ ] Generate only real dataset, resource, metric, uncertainty and agreement tables/figures. Write the ACL paper within the page limit, framed as rationale distillation; explain the v2.3 → v3.0 label-convention finding, the single-definition benchmark, bug-injection exclusions, the small test set, teacher selection and pretraining exposure.
- [ ] Bring README commands and outputs into sync with the finished CLI. Verify a fresh `uv sync --locked`, Ruff, deterministic build and artifact-hash checks, and end-to-end reproduction. Do not present missing runs as results.

**Immediate next step:** approve the v3.0 teacher pilot (6 training contracts, ≤ 12 Codex calls), then inspect the reports.
