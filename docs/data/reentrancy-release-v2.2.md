# Reentrancy release — SPEC v2.2 (provisional split)

Built from the [v2.1 inventory](reentrancy-baseline-v2.1.md) (content `2ba41c2d…`). State: **provisional split with fixed human-review queues**.
It is not frozen: no human label review has been recorded yet, and no teacher
call, training run or model result exists.

Release content fingerprint:
`72e53f148859b0e40f829ba5d567d3c0c58320d28fc203f72c0eb1bf126f086f`.

## How the cohort was built

1. **Eligibility.** A development query needs a PRESENT/ABSENT upstream judgment
   with at least one upstream-reviewed assessment. No-finding negatives count only
   from a source whose protocol covered reentrancy (Salzano; see the
   [revision note](../research/revision-v2.2-2026-09-23.md)).
   Eligible pool: **225 PRESENT (157 groups) / 836 ABSENT (653 groups)**.
2. **Group cap.** At most 3 queries per group and polarity (seeded order): −79.
3. **Split.** Seven-fold StratifiedGroupKFold over groups, strata = collection ×
   verdict; fold 0 held-out, fold 1 validation. Seed 42 passed all gates at the
   first attempt.
4. **Matching.** Inside each partition, every PRESENT query gets one ABSENT
   control: same collection, scope kind and pragma if possible, else fall back
   (collection + scope → scope + pragma → scope → any). 119 exact matches,
   32 scope + pragma, 37 scope only. 606 unmatched negatives are recorded as surplus.

| Partition | PRESENT | ABSENT | PRESENT groups | ABSENT groups |
| --- | ---: | ---: | ---: | ---: |
| Train | 133 | 133 | 108 | 129 |
| Validation | 27 | 27 | 24 | 27 |
| Held-out | 28 | 28 | 25 | 28 |
| **Total** | **188** | **188** | 157 | 184 |

Groups never cross partitions. Supplied scope is identical across polarities in
every partition (FUNCTION 143/143, FILE 45/45 overall).

| Collection | PRESENT | ABSENT |
| --- | ---: | ---: |
| SCRUBD-CD (function scope) | 75 | 143 |
| DAppSCAN (almost all function scope; positives only) | 69 | 0 |
| Salzano, SmartBugs-wild sample (file scope) | 28 | 28 |
| Salzano, ZEUS "vulnerable" collection (file scope) | 7 | 7 |
| ScBench (file scope) | 9 | 10 |

| First pragma | PRESENT | ABSENT |
| --- | ---: | ---: |
| 0.4 | 115 | 149 |
| 0.5 | 17 | 18 |
| 0.6 | 28 | 3 |
| 0.7 | 7 | 0 |
| 0.8 | 18 | 16 |
| unspecified | 3 | 2 |

## Remaining cues (report these, do not hide them)

- DAppSCAN supplies 69 positives and no negatives; their controls come from
  SCRUBD. A model could partly learn DAppSCAN code style. The collection-majority,
  TF-IDF and within-SCRUBD results expose this.
- Pragma 0.6/0.7 is mostly PRESENT (35 vs 3). Report the pragma slice.
- The held-out fold is matched and balanced, so its metrics do not estimate
  real-world prevalence or positive predictive value.

## Human review (you, before freezing)

Queues are fixed and deterministic. Cards are shown in a seeded order that does not
reveal the upstream verdict.

- **Training-label audit:** 44 train cards, up to 5 unique groups per collection ×
  verdict cell (the ZEUS-vulnerable PRESENT cell has only 4 groups).
- **Primary test:** 25 PRESENT-queue and 28 ABSENT-queue held-out cards, at most one
  per group and polarity. Review stops per polarity once 20 are accepted, so about
  40–53 cards.

```bash
uv run python scripts/review_labels.py audit      # training-label audit
uv run python scripts/review_labels.py primary    # held-out primary test
uv run python scripts/review_labels.py primary --status
```

What to check on each card:

- **Blind first.** Decide from the numbered source, scope and check alone.
- **Same property and scope?** The upstream label must be about reentrancy at this
  scope. A negative for another weakness, or for a different function, is not a
  reentrancy negative.
- **Is the file sufficient?** If an imported guard, base contract, callback or
  deployment state that is not in the file decides the answer, record UNKNOWN.
- **Does the mechanism hold?** An external call before a state update is not enough
  by itself; ask whether re-entry can actually break balances/accounting. A
  `nonReentrant` name is not proof of protection. Read-only reentrancy and
  oracle/economic manipulation are out of scope.
- **Lines.** For PRESENT, give the lines you verified (the call and the late state
  update). Never copy lines from the function boundary alone.

Each card writes the blind model input to `data/reviews/current_card.md`. You record
a blind verdict, then the upstream evidence is revealed. You then record the final
verdict, sufficiency, check equivalence, verified vulnerable lines and a one-sentence
rationale. Every card is saved immediately to `data/reviews/reentrancy-v2.2.jsonl`
(gitignored).

## Freeze

```bash
uv run python scripts/build_dataset.py --stage freeze
```

Freeze refuses to run until both queues are complete. It applies these rules:

- **Training audit.** A disagreeing or UNKNOWN card is quarantined together with
  its matched partner, not relabeled. Two or more errors in one cell count as
  systematic: they need a recorded `quarantined_cells` decision in
  `configs/release.yaml`.
- **Primary test.** The first 20 accepted cards per *final* verdict are used, one
  per group. Corrected labels join their final polarity. UNKNOWN cards leave every
  held-out view. The remaining held-out queries form the secondary test.
- **Gates.** It rechecks the group gates (30/5/10) and collection breadth, then
  writes `train`, `validation`, `test_primary` and `test_secondary` parquet files,
  the 30 SmartBugs external positives with independent lines, the reviews, and
  a hashed `dataset_freeze.json`.
