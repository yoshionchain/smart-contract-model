# Decision log

The research decisions behind the project, newest first, each made before the result it
could influence (training decisions before training, the follow-ups before running them).
It documents why the dataset changed from a mixed-source collection (v2.3) to one
expert-verified benchmark (v3.0), and why a second training run, extra seeds and the
faithfulness test were added. Results of both training runs are kept in `results/`.

- **2026-09-26 · Framing and final analyses.** Title *Distilling Explanations, Not Just
  Labels: Can Small Language Models Learn to Justify Smart Contract Vulnerability
  Judgments?*; written for NLP readers without blockchain background (background
  section, running example, no dataset-internal jargon). Run 2 showed all trained
  conditions within ~0.03 test macro-F1, so two analyses are added, declared before
  running: (a) **seeds** 43 and 44 for all four conditions (with run 2 as seed 42) to
  report mean ± spread (Dodge et al. 2020); (b) a **causal faithfulness test** for the
  analysis-first students (Lanham et al. 2023): the verdict is re-decoded after the
  model's own analysis (control), a neutral empty analysis, and the analysis of the
  matched opposite-label contract. No other training change; self-consistency and
  multiple rationales were considered and dropped as out of scope for the deadline.
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
