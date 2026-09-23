# Remaining work

Follow [SPEC.md](SPEC.md) for the experiment and acceptance rules. Work down this list; a checked inventory task does **not** mean the dataset is ready for training. Commands described as *planned* have not been implemented. The submission deadline in the spec is September 30, 2026, 23:59.

## 1. Finish the validated reentrancy dataset (Phase 2)

- [x] Fetch and pin the seven approved source snapshots. Preserve raw source, native non-target findings, provenance, and protected external data.
- [x] Build the v2.1 candidate inventory (scoped queries, comment-blanked source, native evidence, groups, external reservations, statistics, mechanical validation).
- [x] **SPEC v2.2 revision** ([rationale](docs/research/revision-v2.2-2026-09-23.md)): analysis-before-verdict reports, validation macro-F1 checkpoint selection, CGT/FORGE inactive, per-group cap, split-then-match balanced cohorts, Salzano coverage confirmed, shortcut baselines.
- [x] Eligibility (upstream-reviewed evidence only), group cap, seven-fold grouped split, per-partition 1:1 matching, fixed training-audit and primary-test queues: `uv run python scripts/build_dataset.py --stage split`. See the [release card](docs/data/reentrancy-release-v2.2.md): 133/133 train, 27/27 validation, 28/28 held-out.
- [x] Interactive blind-first review tool and freeze stage (with tests and a simulated end-to-end freeze on a throwaway copy).
- [ ] **Human reviewer:** complete the training-label audit (44 cards): `uv run python scripts/review_labels.py audit`. If a cell shows two or more disagreements, decide whether to quarantine the whole stratum (`quarantined_cells` in `configs/release.yaml`).
- [ ] **Human reviewer:** complete the held-out primary queue until 20 accepted per polarity (about 40–53 cards): `uv run python scripts/review_labels.py primary`. Blind verdict first, then evidence, then final verdict, verified lines and rationale.
- [ ] **Version the release inputs:** commit code, configs, schemas and docs so the freeze records an exact Git revision. Keep raw data, reviews and source-containing outputs out of Git.
- [ ] **Freeze:** `uv run python scripts/build_dataset.py --stage freeze`. It fails with the missing work listed until both queues are complete and all gates pass. **No teacher generation before this gate passes.**

## 2. Generate and audit teacher supervision (Phase 3)

- [ ] **Implement with mocks only:** teacher prompt asking for the v2.2 evidence-ordered `analysis` first (external calls → state changes → guards/ordering → conclusion last, citing lines); pinned Codex CLI runner (`gpt-5.6`, medium effort, low verbosity), isolated temporary directory/read-only sandbox, disabled inherited context/tools/network, sentinel isolation preflight, strict batch/report schema, up-to-five batching, one retry, terminal UNSUPPORTED, resumable cache, usage log, and zero-call dry run. Test malformed/partial batches, stale cache, and prohibited access without consuming subscription allowance.
- [ ] **Approval required for the real pilot:** after freeze and isolation tests, show the exact pilot command, up-to-six selected training queries (at most three per polarity), at-most-two first-pass invocations, retry ceiling, and estimated tokens. Wait for explicit approval for that run. Inspect every output, then freeze teacher/student prompts and schemas using training data only.
- [ ] **Approval required for each production run:** show exact train/validation commands and dry-run counts/usage estimate, then wait for explicit approval. Generate only frozen train/validation queries. Preserve valid partial work, log rejects/UNSUPPORTED, and never use test/external source as teacher input.
- [ ] **Human reviewer:** audit up to ten accepted training reports (up to five per polarity) for verdict consistency, locations, grounding, exploit plausibility, and mitigation. Record weaknesses without hand-picking automatically valid reports out of the cohort.

## 3. Build the matched student dataset (Phase 4)

- [ ] **Implement:** canonical chat formatting and assistant-only loss for Label-SFT and Report-SFT. Enforce the 6,000-token source budget, 480-token report target, and 8,192-token complete-sequence limit with the pinned tokenizer/template; exclude rather than truncate overlength examples.
- [ ] **Freeze:** identical sorted accepted train/validation IDs for both conditions in `shared_cohort.json`; reject unsupported/invalid/overlength items from both. Recheck train/validation polarity-group and source-breadth gates and report acceptance bias. Stop if a gate fails.

## 4. Train the student conditions (Phase 5)

- [ ] **Implement and smoke-test:** normal Python QLoRA modules and a documented Google Colab CLI workflow using the exact model, adapters, hyperparameters and seeds in SPEC, with per-epoch greedy validation macro-F1 checkpoint selection (v2.2). Save effective configs, tokenizer/prompt hashes, logs, and adapters.
- [ ] **Approval required for real Colab jobs:** show the exact commands, runtime/resources, dataset and cohort hashes, and expected outputs. Run both SFT conditions only after explicit approval. Keep Base as the unchanged model.

## 5. Evaluate without tuning on held-out data (Phase 6)

- [ ] **Implement and run:** the (scope, pragma) majority and TF-IDF logistic-regression baselines fitted on train only, plus the collection-majority baseline.
- [ ] **Implement and run:** deterministic Base-Label, Base-Report, Label-SFT, and Report-SFT inference on the same frozen reviewed-primary IDs and on the whole matched held-out fold. Report binary PRESENT/ABSENT macro-F1, positive precision/recall, invalid-output/schema rates, paired group-bootstrap uncertainty, and raw predictions. Invalid outputs count as misses under SPEC rules.
- [ ] **Implement and run:** secondary held-out and eligible SmartBugs/FORGE external views separately. Score localization only against independent verified line evidence, never teacher lines or function bounds as gold. Export denominator-aware metrics and error strata; do not retune from test results.

## 6. Human report comparison (Phase 7)

- [ ] **Implement:** select up to 25 reviewed-primary queries and produce randomized, blinded paired Base-Report/Report-SFT cards with a hidden key and the SPEC scoring rubric.
- [ ] **Human reviewer:** rate the blinded cards before unblinding. Then score with actual ratings, denominators, paired comparisons, and any documented second-rater agreement.

## 7. Paper and reproducibility (Phase 8)

- [ ] Generate only real dataset, resource, metric, uncertainty, and human-rating tables/figures. Write the ACL paper within the SPEC page limit, explain scoped ABSENT/UNKNOWN, source concentration, compiler-era limits, incomplete ancestry, teacher noise, and public-pretraining exposure.
- [ ] Bring README commands and outputs into sync with the finished CLI. Verify a fresh `uv sync --locked`, full `uv run pytest`, Ruff, deterministic build/freeze and artifact-hash checks, and documented end-to-end reproduction. Do not present missing runs as results.

**Immediate next step:** the human review of both queues, then freeze. Meanwhile the teacher runner can be built and tested with mocks only.
