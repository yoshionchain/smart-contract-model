# Remaining work

Work down this list. [SPEC.md](SPEC.md) is the detailed guideline; its decision log records why things are the way they are. Commands described as *planned* are not implemented yet. Deadline: September 30, 2026, 23:59.

## 1. Dataset (done, v3.0)

- [x] Switch to the expert-verified Ca' Foscari benchmarks (one definition): exclude bug-injected and overlength contracts, de-duplicate, group clones and RSD scenario families, grouped split, 1:1 balance per partition and collection. 78/78 train, 17/17 validation, 30/30 test; reproducible (`data/manifests/`).
- [x] Keep the v2.3 mixed-source teacher result for the paper (`data/manifests/teacher_v2.3_mixed_sources.json`: 62% agreement; SCRUBD and SmartBugs-wild conventions conflict).

## 2. Teacher supervision

- [x] Runner implemented and checked with mocks, dry runs and a real v2.3 pilot and production run (isolation, retries, resumability and usage logging work; 322/322 calls valid).
- [x] **v3.0 pilot (2026-09-25):** 6 training contracts (3 real, 3 RSD; 3 per label), 6 calls, no retries, no tool use; 6/6 agree with the expert labels; all cited lines are code; analyses apply the three-part definition. `teacher_v2.txt` unchanged, pending the owner's go to freeze it.
- [x] **First v3.0 production (2026-09-25):** 93.7% train agreement (148/158), 90% validation. Four train disagreements came from too-broad read-only wording (public getters); assumption 4 narrowed, release rebuilt (`7349c043…`: 78/78, 17/17, 30/30), first run kept in `runs/teacher-v3.0-first/`.
- [x] **Production rerun (2026-09-26):** 190/190 calls valid, no retries. Train agreement 94.9% (148/156): 70/78 pairs survive → **140 training examples** (37 / 58 groups, gate passes). Validation 30/34 (three delegatecall scenarios ABSENT, one UNSUPPORTED — RQ3 finding; all 34 still serve checkpoint selection). Prompt `teacher_v2.txt` and the data definition are frozen.
- [x] **Teacher ceiling (2026-09-26):** after a Codex outage (two calls failed before any answer, nothing spent), 60/60 test calls valid: 56/60 agree, macro-F1 0.933 (four reentrant contracts judged ABSENT). Used only for the ceiling row and RQ3.

## 3. Build the matched student dataset (Phase 4, done)

- [x] Chat formatting with the pinned Qwen3 template for Label-SFT, Report-SFT and Report-SFT-VF (system prompt per format, identical user payload, prompt/completion records for assistant-only loss); 140 shared train IDs (70 pairs, 37/58 groups, gate passes), all 34 validation and 60 test prompts per format; no truncation (longest 6,130 tokens); reproducible (`data/manifests/student_*.json`).

## 4. Train the student conditions (Phase 5)

- [x] **Implemented and smoke-tested:** `scripts/train.py` (BF16 LoRA via TRL/PEFT, completion-only loss, per-epoch adapters, post-training validation macro-F1 selection, full run records) and `scripts/colab.py` (H100 VM, bundle upload, locked `uv` env, detached job, status, fetch, stop). CPU smoke run passes; TRL tokenization matches all 420 train records and the loss covers only the answers.
- [ ] **Approval required for the Colab H100 job:** `uv run python scripts/colab.py up`, then `train` (all three conditions in sequence), `status`, `fetch`, `down`. First check at `up` that the VM's driver runs the CUDA 12.6 `torch` build. (Approved 2026-09-26: BF16 LoRA, first run.)

## 5. Evaluate without tuning on held-out data (Phase 6)

- [ ] **Implement and run:** baselines fitted on train only (constant, collection majority, Solidity-version majority, TF-IDF logistic regression).
- [ ] **Implement and run:** deterministic Base-Label, Base-Report, Label-SFT, Report-SFT and Report-SFT-VF inference on the 60 test contracts, next to the baselines and the teacher ceiling. Macro-F1, PRESENT precision/recall, invalid rates, paired group-bootstrap intervals (Report-SFT − Label-SFT, Report-SFT − Report-SFT-VF, each − its base format), slices by collection and version, grounding/faithfulness (cited lines exist and are code; the conclusion states the report's own verdict), teacher–label agreement, raw predictions.

## 6. Optional human rating (Phase 7)

- [ ] Only if time allows: blinded Base-Report vs Report-SFT cards on up to 20 test contracts, rated for grounding and consistency.

## 7. Paper and reproducibility (Phase 8)

- [ ] Generate only real dataset, resource, metric, uncertainty and agreement tables/figures. Write the ACL paper within the page limit, framed as rationale distillation; explain the v2.3 → v3.0 label-convention finding, the single-definition benchmark, bug-injection exclusions, the small test set, teacher selection and pretraining exposure.
- [ ] Bring README commands and outputs into sync with the finished CLI. Verify a fresh `uv sync --locked`, Ruff, deterministic build and artifact-hash checks, and end-to-end reproduction. Do not present missing runs as results.

**Immediate next step:** approve the Colab H100 training job, then implement evaluation (Phase 6) while it runs.
