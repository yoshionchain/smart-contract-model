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
- [x] **First training run (2026-09-26):** A100-40GB (H100 not available to the account), BF16 LoRA, commit `c530723`, ~5 min per condition (105 steps). Validation macro-F1 of the selected epochs: Label-SFT 0.911 (epoch 3), Report-SFT 0.647 (epoch 3), Report-SFT-VF 0.728 (epoch 2).

- [x] **Run 2 (2026-09-26):** 6 epochs, four conditions incl. Multi-SFT, A100. Test macro-F1: Label-SFT 0.800, Report-SFT-VF 0.800, Multi-SFT 0.796, Report-SFT 0.766 (run 1: 0.697), Multi-SFT report mode 0.733; all SFT–SFT differences include zero; Report-SFT − Base-Report on RSD +0.343 [+0.186, +0.462]. Results in `results/run2-multi/`.

## 5. Evaluate without tuning on held-out data (Phase 6)

- [x] **Implemented and checked:** `scripts/predict.py` (GPU; all five modes, strict parsing, raw outputs kept; CPU smoke passes) and `scripts/evaluate.py` (baselines fitted on train, teacher ceiling, macro-F1 and slices, paired group bootstrap, grounding/faithfulness; mechanically checked on synthetic inputs outside `results/`).
- [x] **First evaluation (2026-09-26):** test macro-F1 Label-SFT 0.798, Report-SFT-VF 0.790, Report-SFT 0.697, Base-Report 0.653, Base-Label 0.425, teacher 0.933, TF-IDF 0.707 (`results/`). Only Label-SFT − Base-Label is clearly positive; report conditions lag on RSD.

- [x] **Implemented and smoke-tested (2026-09-26):** extra-seed training/prediction and the causal faithfulness test; chunked upload of adapters for resumed VMs.
- [ ] **Run (approval required):** seeds 43/44 for four conditions, predictions, faithfulness test; then `evaluate.py`.

## 6. Optional human rating (Phase 7)

- [ ] Only if time allows: blinded Base-Report vs Report-SFT cards on up to 20 test contracts, rated for grounding and consistency.

## 7. Paper and reproducibility (Phase 8)

- [ ] Generate only real dataset, resource, metric, uncertainty and agreement tables/figures. Write the ACL paper within the page limit, framed as rationale distillation; explain the v2.3 → v3.0 label-convention finding, the single-definition benchmark, bug-injection exclusions, the small test set, teacher selection and pretraining exposure.
- [ ] Bring README commands and outputs into sync with the finished CLI. Verify a fresh `uv sync --locked`, Ruff, deterministic build and artifact-hash checks, and end-to-end reproduction. Do not present missing runs as results.

**Immediate next step:** approve the A100 session for seeds 43/44 and the faithfulness test, then the paper and presentation.
