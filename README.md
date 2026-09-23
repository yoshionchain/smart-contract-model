# Synthetic Audit Distillation

A university NLP experiment on teaching a small code language model to assess
reentrancy in Solidity and generate grounded structured reports. The experiment
compares an unchanged small model with verdict-only and report-supervised
fine-tuning. REENTRANCY is the sole active check.
[`SPEC.md`](SPEC.md) is the authoritative experimental specification.

**Current status (SPEC v2.2): the balanced, group-split release and its human-review
queues are built; human review and freeze are pending.** The v2.1 inventory combines
all seven pinned sources and builds contamination groups. From it, the v2.2 stage
keeps upstream-reviewed evidence, splits groups 5/7–1/7–1/7 and balances every
partition 1:1 by matched sampling: 133/133 train, 27/27 validation, 28/28 held-out.
No explanatory targets, teacher calls, model weights, or training runs exist yet.
See the [release card](docs/data/reentrancy-release-v2.2.md) and the
[v2.2 revision](docs/research/revision-v2.2-2026-09-23.md).

PRESENT/ABSENT refers to one check at one native scope under stated assumptions.
ABSENT does not mean the source is secure. Missing labels remain UNKNOWN.

## Setup and build

Use Python 3.12 and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked
uv run pytest
uv run ruff check src tests scripts
uv run python scripts/fetch_data.py
uv run python scripts/build_dataset.py --stage inventory
uv run python scripts/validate_dataset.py
uv run python scripts/build_dataset.py --stage split     # v2.2 release + review queues
```

After the human review (below), freeze the dataset:

```bash
uv run python scripts/build_dataset.py --stage freeze
```

Sources and revisions are in [`configs/project.yaml`](configs/project.yaml).
Fetch verifies existing checkouts and expands requested sparse paths; it refuses
dirty checkouts or revision/origin mismatches. It does not reset local work.
`--source cgt` (repeatable) fetches selected sources. Build also verifies the
complete selected Git subtrees, including filenames with spaces/non-ASCII text.

The build uses the pinned student tokenizer, downloading it on first use if
necessary, without model weights. With the tokenizer cached, set
`HF_HUB_OFFLINE=1` for an offline rebuild. The build takes several minutes.
Both commands accept `--config PATH`; build accepts `--output-dir PATH`.
Stages: `inventory` (v2.1 candidates, several minutes), `split` (seconds; settings
in [`configs/release.yaml`](configs/release.yaml)) and `freeze` (refuses to run until
both review queues are complete and all gates pass). Tests run offline with tiny fixtures.

## Outputs

The v2.2 release lives in `data/processed/reentrancy-v2.2/`: `release_queries.jsonl`
(the balanced cohort with partition and match pair), `eligible_pool.jsonl`,
`release_exclusions.jsonl`, `split_assignments.jsonl`, `split_attempts.json`, the two
review queues, `release_statistics.json` and a hashed `release_manifest.json`.
Freeze adds `train`/`validation`/`test_primary`/`test_secondary.parquet`,
`external_smartbugs.jsonl`, `reviews.jsonl` and `dataset_freeze.json`.

The v2.1 inventory artifacts live in `data/processed/reentrancy-v2.1/`. Raw checkouts and large generated
artifacts are gitignored. Small reproducibility snapshots and the dataset card
live in [`data/manifests/`](data/manifests/) and [`docs/data/`](docs/data/).

| Artifact | Contents |
| --- | --- |
| `artifacts.parquet` | All source artifacts/aliases, sanitized full code, hashes, ancestry, original collection, source role |
| `assessments.parquet` | Every available native judgment, its exact annotation reference, scope, evidence tier, and original coordinates |
| `queries.parquet` | Coalesced, mechanically resolved check/scope candidates; `training_ready` is always false at this stage |
| `exclusions.jsonl` | Assessment-level unknown-label, source, scope, length, and source-eligibility exclusions |
| `ingestion_issues.jsonl` | Missing published code and audit reports without available source |
| `conflicts.jsonl` | Unresolved opposing native judgments, distinguished by property provenance |
| `groups.jsonl`, `group_edges.jsonl` | Project/deployment, lexical, skeleton, and clone isolation; inactive raw matches are marked explicitly |
| `dataset_statistics.json`, `.csv` | Candidate counts, evidence support, scope/source/polarity matrices, compiler-era screen, and exclusions |
| `effective_config.json`, `taxonomy.json`, `provenance.json` | Settings, reentrancy mappings, source pins, license-notice hashes, tokenizer and implementation provenance |
| `dataset_manifest.json` | File hashes, deterministic data fingerprint, inventory state, and unresolved readiness gates |

The [inventory dataset card](docs/data/reentrancy-baseline-v2.1.md) records the actual
counts, quality limits, reproducibility fingerprint, and next curation steps.

The manifest is published last. Inspection verifies all its file hashes and
rejects incomplete/modified builds. Rebuilding preserves separately authored
`reviews.jsonl`. The inventory command refuses to overwrite frozen/split output or a baseline
from an incompatible protocol. Obsolete generated baselines have been removed.
It does not create empty training/test files that could be mistaken for a release.

The [v2.1 JSON schemas](schemas/v2.1/) describe the inventory evidence records; the
[v2.2 schemas](schemas/v2.2/) describe release queries, human review records and the
semantic report, whose `analysis` field comes before the verdict. `scoped_reports.py` validates reports without generating them;
its PRESENT/ABSENT contract rejects legacy class outputs. Teacher transport and
generation remain later work. Parquet assessment
`metadata` is an Arrow string map; `read_records` in `data/inventory.py` restores
it to a Python dictionary. Re-export schemas with:

```bash
uv run python -m audit_distill.data.schema
```

## Human label review (v2.2)

Only a person runs these commands; an assistant must never create review records.

```bash
uv run python scripts/review_labels.py audit      # training-label audit, 44 cards
uv run python scripts/review_labels.py primary    # held-out primary test, ~40-53 cards
uv run python scripts/review_labels.py primary --status
```

Keep `data/reviews/current_card.md` open in your editor. For each card you first
record a verdict from the blind model input; then the upstream evidence is revealed
and you record the final verdict, input sufficiency, check equivalence, verified
vulnerable lines and a one-sentence rationale. Each card is saved immediately to
`data/reviews/reentrancy-v2.2.jsonl`; stop with `q` or Ctrl-C and rerun to continue.

## Boundaries and remaining work

- Only upstream-reviewed evidence is eligible. CGT stays UNVERIFIED and FORGE's
  modern challenge is unavailable in v2.2; both remain ingested for provenance
  and leakage reservation. Non-target findings never supply reentrancy negatives.
- Check equivalence, context sufficiency and execution assumptions are checked by
  the sampled human training-label audit and the full review of the primary test,
  not assumed. Systematic audit errors quarantine a whole stratum.
- Balancing discards surplus negatives; nothing is relabeled or synthesized.
  DAppSCAN has positives only and 0.6/0.7-pragma code is mostly PRESENT, so the
  evaluation reports lexical/metadata baselines and collection/pragma slices.
- Groups are the inventory's conservative components; unknown project ancestry,
  public pretraining exposure and old-code concentration remain limitations.
  The lexical resolver does not compile code or verify guards.
- Teacher generation and Colab training are unimplemented and each real run
  needs explicit approval after freeze.

## Research protocol

The primary outcome is binary macro-F1 over PRESENT/ABSENT, with positive
precision/recall, invalid-output accounting, and group-bootstrap uncertainty.
The reviewed-test target remains 20 positives and 20 negatives; minimum support
is 30 training, 5 validation and 10 reviewed-test groups per polarity. These are
feasibility gates, not a power calculation. The later blinded report comparison
keeps its 25-query budget and evaluates grounding as well as structured validity.

The main corpus spans compiler eras. The modern FORGE challenge is inactive in v2.2. Recent benchmark papers and incident
lists are research leads, not newly admitted training data. See the
[revision record](docs/research/reentrancy-decision-2026-09-22.md).

## Where to go next

Follow [todo.md](todo.md) in order. It distinguishes implementation work, human
review and explicit approval for real model runs. The immediate milestone is the
human review of both queues and a hashed dataset freeze.

The maintained documentation is:

- [SPEC.md](SPEC.md): authoritative experiment and acceptance requirements.
- [todo.md](todo.md): ordered remaining work and human responsibilities.
- [Release card](docs/data/reentrancy-release-v2.2.md): the balanced v2.2 cohort, cues and review steps.
- [Inventory card](docs/data/reentrancy-baseline-v2.1.md): v2.1 candidate counts and limitations.
- [v2.2 revision](docs/research/revision-v2.2-2026-09-23.md): what changed on September 23 and why.
- [Revision rationale](docs/research/reentrancy-decision-2026-09-22.md): why the scope changed.

Only the current pipeline, schemas and configs remain. Raw sources, native
non-target evidence and protected contexts are still required for provenance and
leakage prevention; they were not removed with the obsolete experiments.
