# Remaining work

Work down this list. [SPEC.md](SPEC.md) is the detailed guideline; its decision log records why things are the way they are. Commands described as *planned* are not implemented yet. Deadline: September 30, 2026, 23:59.

## 1. Dataset (done)

- [x] Fetch the seven pinned sources and build the candidate inventory with leakage groups and mechanical validation.
- [x] Build the final release: upstream-reviewed labels under the SWC-107 convention, group cap, grouped split, 1:1 matched balancing. 134/134 train, 27/27 validation, 27/27 test, 30 SmartBugs external positives. See the README's dataset section.

## 2. Generate and audit teacher supervision (Phase 3)

- [ ] **Implement with mocks only:** label-blind teacher prompt (analysis first: external calls → state changes → guards/ordering → conclusion last, citing lines; then its own verdict); pinned Codex CLI runner (`gpt-5.6`, medium effort, low verbosity) in an isolated empty temp dir with read-only sandbox, disabled tools/web/inherited instructions and a sentinel isolation preflight; strict batch/report schema; up to five queries per call; one retry for invalid output only; acceptance only when the teacher's verdict equals the label, with the matched partner removed on rejection; resumable cache; usage log; zero-call dry run. Check it with mock responses (malformed/partial batches, disagreements, stale cache) without using the subscription.
- [ ] **Approval required for the real pilot:** show the exact pilot command, the up-to-six training queries (at most three per label), at most two invocations, the retry ceiling and estimated tokens, then wait for approval. Inspect every output, then freeze the prompts using training data only.
- [ ] **Approval required for each production run:** show the exact train/validation commands and dry-run usage estimate, then wait for approval. Generate only train/validation; preserve valid partial work; report agreement/disagreement rates per collection and label (the label-noise estimate); never send test or external data to the teacher.
- [ ] **Optional (~10 reports):** spot-check accepted teacher reports for grounding and correct lines, without removing reports from the cohort.

## 3. Build the matched student dataset (Phase 4)

- [ ] **Implement:** canonical chat formatting and assistant-only loss for Label-SFT and Report-SFT. Enforce the 6,000-token source budget, 480-token report target, and 8,192-token complete-sequence limit with the pinned tokenizer/template; exclude rather than truncate overlength examples.
- [ ] **Freeze:** identical sorted accepted train/validation IDs for both conditions in `shared_cohort.json`; reject unsupported/invalid/overlength items from both. Recheck train/validation polarity-group and source-breadth gates and report acceptance bias. Stop if a gate fails.

## 4. Train the student conditions (Phase 5)

- [ ] **Implement and smoke-test:** normal Python QLoRA modules and a documented Google Colab CLI workflow using the exact model, adapters, hyperparameters and seeds in SPEC, with per-epoch greedy validation macro-F1 checkpoint selection. Save effective configs, tokenizer/prompt hashes, logs, and adapters.
- [ ] **Approval required for real Colab jobs:** show the exact commands, runtime/resources, dataset and cohort hashes, and expected outputs. Run both SFT conditions only after explicit approval. Keep Base as the unchanged model.

## 5. Evaluate without tuning on held-out data (Phase 6)

- [ ] **Implement and run:** the (scope, pragma) majority and TF-IDF logistic-regression baselines fitted on train only, plus the collection-majority baseline.
- [ ] **Implement and run:** deterministic Base-Label, Base-Report, Label-SFT, and Report-SFT inference on the same test IDs. Report binary PRESENT/ABSENT macro-F1, positive precision/recall, invalid-output/schema rates, paired group-bootstrap uncertainty, and raw predictions. Invalid outputs count as misses under SPEC rules.
- [ ] **Implement and run:** the SmartBugs external view separately. Score localization only against upstream line annotations on the exact file (13 test and 30 SmartBugs positives), never teacher lines or function bounds as gold. Export denominator-aware metrics and error strata; do not retune from test results.

## 6. Human report comparison (Phase 7)

- [ ] **Implement:** select up to 25 test queries and produce randomized, blinded paired Base-Report/Report-SFT cards with a hidden key and the SPEC scoring rubric.
- [ ] **Human reviewer:** rate the blinded cards before unblinding. Then score with actual ratings, denominators, paired comparisons, and any documented second-rater agreement.

## 7. Paper and reproducibility (Phase 8)

- [ ] Generate only real dataset, resource, metric, uncertainty, and human-rating tables/figures. Write the ACL paper within the SPEC page limit, explain scoped ABSENT, unverified upstream labels under the SWC-107 convention, source concentration, compiler-era limits, incomplete ancestry, teacher noise, and public-pretraining exposure.
- [ ] Bring README commands and outputs into sync with the finished CLI. Verify a fresh `uv sync --locked`, Ruff, deterministic build and artifact-hash checks, and documented end-to-end reproduction. Do not present missing runs as results.

**Immediate next step:** build the label-blind teacher runner with mocks and a zero-call dry run, then ask for approval of the real pilot.
