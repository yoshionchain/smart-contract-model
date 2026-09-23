# SPEC v2.2 revision, September 23, 2026

The user approved these changes before any teacher generation, model training or
human label review. No model results informed them. SPEC.md is authoritative;
this note records why each change was made.

## Decisions

1. **Analysis before verdict.** The report's first field is now `analysis`
   (≤1,200 characters), followed by `verdict` and the verdict-dependent fields.
   With greedy decoding a verdict-first report commits to the answer before any
   explanation is generated, so RQ2 could only test rationales as auxiliary
   training signal. Analysis-first tests whether writing a grounded analysis
   *before* deciding helps a small model. The known risk (errors in the analysis
   propagating to the verdict) is a legitimate outcome, so H3 is now an open
   question. The optional verdict-first third adapter was declined.
2. **Checkpoint selection by validation macro-F1.** Report-SFT validation loss is
   dominated by prose tokens and is not comparable with Label-SFT loss. Both
   adapters now keep the epoch checkpoint with the best greedy-decoded validation
   binary macro-F1 (ties: lower validation loss, then earlier epoch).
3. **CGT and FORGE are not active.** CGT evidence stays UNVERIFIED (its original
   assessment protocol was not established), so it could never enter SFT. The
   modern FORGE challenge is reported as unavailable. Both remain pinned and
   ingested for provenance and leakage reservation.
4. **Balanced, matched cohorts.** The eligible upstream-reviewed pool is 225
   PRESENT / 836 ABSENT queries. Before any model result, a probe showed that
   scope kind and first pragma alone predict the label (grouped-CV macro-F1 0.62,
   versus 0.44 for constant ABSENT): 93% of file-scope queries are ABSENT and
   0.6/0.7 code is mostly PRESENT. Each partition is therefore balanced 1:1 by
   matched sampling on (collection, scope kind, pragma) with a fixed fallback
   hierarchy. On the matched pool the scope/pragma probe falls to chance (0.50).
   Surplus negatives are recorded as `balancing_surplus`, never relabeled.
   A bag-of-words probe still reached about 0.73, so lexical baselines are required.
5. **Per-group cap.** At most three queries per group and polarity are kept.
   Two DAppSCAN projects contributed 13 positives each; functions of one project
   are not independent evidence and would dominate a small held-out fold.
6. **Split then match.** Groups are split first (seven-fold StratifiedGroupKFold
   on collection × verdict strata), then matched inside each partition, so every
   case and its control share a partition. The held-out fold must also offer at
   least 20 groups per polarity so the reviewed 20/20 target is reachable.
7. **Salzano negative coverage is confirmed at the stratum level.** Salzano et al.
   (arXiv:2505.15756) annotated every instance against all DASP Top-10 categories,
   double-validated every not-vulnerable judgment and resolved all conflicts by
   consensus. Their no-finding files are therefore reentrancy negatives at file
   scope. The sampled training-label audit still checks individual cards.
8. **Reporting.** The whole held-out fold (upstream-reviewed, matched) is reported
   with the same prominence and uncertainty as the reviewed primary subset. Add a
   scope/pragma majority baseline, a TF-IDF logistic-regression baseline, a
   valid-output-only macro-F1 next to the strict score, and slices by collection,
   scope kind and pragma, including the within-SCRUBD slice.

## What does not change

Teacher and student models, QLoRA hyperparameters, token budgets, comment
blanking, scope rules, grouping/leakage rules, the human-review protocols (blind
first, then reveal), invalid-output handling and the group bootstrap are unchanged.
The v2.1 inventory artifacts are reused unchanged as the release input.

## Honest limits introduced or kept

- Balancing discards 606 real negatives and the group cap discards 79 queries;
  both are deterministic, recorded, and decided before results.
- DAppSCAN has no negatives. Its positives are matched to SCRUBD function-scope
  controls on scope and pragma, but collection style remains a possible cue;
  the collection-majority and lexical baselines and the SCRUBD slice expose it.
- 0.6/0.7-pragma code remains mostly PRESENT (35 vs 3). Report the pragma slice.
- Matched balance means held-out metrics do not estimate real-world prevalence.
