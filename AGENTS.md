# AGENTS.md

## Project

This repository implements the university research project **Synthetic Audit Distillation: Training a Small Language Model to Assess Reentrancy and Generate Grounded Reports**.

The goal is a small, rigorous, reproducible NLP experiment—not a production smart-contract auditor. The project studies whether a small code language model can learn scoped reentrancy assessment and grounded structured report generation from teacher-generated natural-language supervision attached to real, labeled Solidity code.

SPEC v2.2 defines scoped PRESENT/ABSENT reentrancy assessment and grounded
structured reports whose `analysis` field precedes the verdict. REENTRANCY is the
only active check. The CLI builds the unchanged v2.1 candidate inventory under
`data/processed/reentrancy-v2.1/` and, from it, the v2.2 balanced, matched,
group-split release and fixed human-review queues under
`data/processed/reentrancy-v2.2/`. Keep all native evidence and external
reservations; inactive findings never become extra targets or reentrancy negatives.
CGT and FORGE stay ingested for provenance/leakage but are inactive. Follow
`todo.md` for remaining work. Real human label review (via
`scripts/review_labels.py`, by a person only) and freeze are still required before
training readiness can be claimed. An assistant must never run the review tool
or write review records.

## Source of truth

`SPEC.md` is the authoritative project specification. Read it completely before making architectural, methodological, dataset, model, training, or evaluation decisions.

Rules:

- Do not silently change anything marked locked in `SPEC.md`.
- Do not broaden the experiment or add product features outside the explicit scope.
- Do not change datasets, target classes, split rules, teacher/student models, schemas, evaluation metrics, or training settings without explicit user approval.
- Do not "improve" the methodology by substituting a different design unless the current design is impossible; if a conflict or blocker appears, explain it before changing anything.
- Never edit `SPEC.md` merely to make the implementation match the code. Implementation must match the spec.
- If this file and `SPEC.md` conflict on a research or experimental decision, `SPEC.md` wins.

## Working style

Build complex things in the simplest reliable way. Prefer direct, readable implementations over framework-heavy abstractions.

- Keep the repository understandable to another student/reviewer.
- Favor reproducibility, explicit data flow, deterministic behavior, and inspectable artifacts.
- Keep core logic under `src/audit_distill/`; scripts should be thin CLI entry points.
- Avoid giant modules and hidden state.
- Avoid premature abstraction. Introduce helpers/modules only when they make the experiment clearer or safer.
- Do not add a database, web app, API server, frontend, RAG system, agent framework, or smart-contract tooling unless the spec is explicitly revised.
- Prefer boring, dependable research software over clever infrastructure.

## Python and environment

- Use Python 3.12 unless an ML dependency truly requires 3.11; document any downgrade.
- Use `uv` for all dependency/environment management.
- Use `pyproject.toml` as the dependency source of truth. Do not maintain a separate `requirements.txt`.
- Use type hints throughout new code.
- Use Pydantic for structured configuration/data/report models where appropriate.
- Use `pathlib` for filesystem paths.
- Use standard `logging` for pipelines; use `rich`/`tqdm` for useful progress display.
- Use JSONL/Parquet/CSV for persisted research artifacts as defined in the spec.
- Keep experiment settings in YAML/config files rather than scattered constants.
- Pin working dependencies in `uv.lock`.

## Research integrity and leakage prevention

Treat experimental correctness as more important than convenience.

- Never allow known project, source-hash, lexical-identity, or declared clone-group overlap across development partitions and protected external data.
- Preserve unknown project ancestry explicitly; a family hash or different deployment address does not prove project independence.
- Blank all comments in every corpus while preserving coordinates and quoted literals.
- Keep PRESENT, ABSENT, and UNKNOWN evidence distinct; only known compatible judgments become supervised queries.
- Unannotated DAppSCAN files, missing labels, tool silence, and non-target-only findings do not establish ABSENT.
- Never lift a negative function/subtype judgment to a whole-file/family negative. Preserve the exact assessed check, scope, and assumptions.
- Never claim ABSENT means the source is secure. `NONE` is a legacy verdict class; v2.1/v2.2 retain it only as the negative report's severity value.
- Retain compatible multiple reentrancy findings/scopes per source; consolidate duplicate support without dropping distinct scoped judgments.
- Do not count assistant-generated review as human label validation. Human decisions, conflict resolutions, and primary-test membership must be inspectable and frozen before model runs.
- Never use test results to tune the teacher prompt, split, training hyperparameters, or preprocessing.
- Never manually cherry-pick generated teacher annotations beyond the declared automatic validation/retry rules.
- Never silently truncate overlength Solidity examples; exclude them according to the spec and record the count.
- Preserve line numbering semantics exactly because localization is an evaluated task.
- Record provenance, versions, hashes, seeds, and effective configs for every important run.

## Teacher annotation rules

The teacher is **GPT-5.6 Sol through Codex CLI**, using the user's ChatGPT subscription.

Locked behavior:

- model argument: `gpt-5.6`
- reasoning effort: `medium`
- output verbosity: `low`
- up to 5 examples per Codex invocation (partial final batches allowed)
- ephemeral execution
- read-only sandbox
- no approval prompts
- no agent network/tool access; host model-service authentication remains available
- Codex CLI 0.154.0, disabled tools/context inheritance, restricted filesystem with isolation preflight
- empty temporary working directory per invocation
- schema-constrained output
- at most one retry for failed examples
- resumable generation; never regenerate valid work unnecessarily

The annotation runner must isolate the teacher from repository context, AGENTS files, external audit reports, web access, scanners, and unrelated local files. The teacher receives only the scoped query/source/assumptions, known verdict, and annotation rules specified in `SPEC.md`. It must be able to return UNSUPPORTED without inventing a report; this rejects the query from both SFT cohorts and never changes a reference label.

Do not add an OpenAI API dependency or automatic API fallback. If Codex subscription limits become a blocker, stop and report it to the user.

### Resource-use gate

Do not consume meaningful Codex subscription allowance without explicit user approval for that run.

You may implement and test the annotation pipeline using dry-run mode and tiny mocked fixtures. Before the real availability-aware pilot (up to six scoped queries) or any production teacher generation, show the user exactly what command will be run and what it will consume, then wait for approval. The v2.2 dataset freeze and support/review gates must pass first.

## Training rules

The student is the exact model and QLoRA setup locked in `SPEC.md`.

- Canonical training code must be normal Python modules/scripts, not notebook-only code.
- Training must work through Google Colab CLI but should remain locally understandable and smoke-testable.
- Do not run a real GPU training job or provision a paid/limited Colab runtime without explicit user approval.
- Small CPU/local smoke tests with tiny fixtures are fine when they do not consume meaningful external resources.
- Save effective configs, checkpoints/logging metadata, and output adapters according to the spec.

## Testing

Testing is part of the implementation, not cleanup work.

At minimum preserve all invariants listed in `SPEC.md`, especially:

- canonical check mapping, scope resolution, and evidence-based filtering;
- explicit negative coverage and UNKNOWN handling;
- scope-aware duplicate/conflict handling;
- deterministic line numbering;
- SmartBugs leakage stripping without line-count changes;
- project/hash/clone-group split isolation and external reservations;
- schema validation rules;
- invalid prediction behavior and binary macro-F1 over PRESENT/ABSENT;
- localization scoring;
- metric correctness.

Use `pytest`. When fixing a bug in an invariant, add or update a regression test.

Before considering a phase complete, run the relevant tests. The repository-wide default check is:

```bash
uv run pytest
```

## Implementation order

Follow the eight phases in `SPEC.md` in order:

1. Repository foundation
2. Data ingestion
3. Teacher pipeline
4. Student dataset formatting
5. Training
6. Evaluation
7. Human evaluation support
8. Paper assets and reproducibility

Do not jump ahead in a way that hides an unresolved earlier-phase assumption.

For each phase:

1. read the relevant `SPEC.md` sections;
2. implement the smallest complete version that satisfies them;
3. add/maintain tests;
4. run checks;
5. inspect generated artifacts where applicable;
6. report what was completed, any deviations, and the exact next step.

## External downloads and upstream data

It is acceptable for the data-fetch scripts to obtain the pinned public sources approved in SPEC v2.1/v2.2: DAppSCAN-source, SCRUBD-CD, Salzano's corpus, selected CGT subsets, ScBench, SmartBugs Curated, and FORGE-Curated. Respect their separate evidence and development/external roles. Make the process deterministic and record exact upstream revisions and original collection ancestry.

Do not commit raw upstream datasets if the spec says they should remain local/gitignored.

If an upstream repository format has changed and the parser cannot be implemented exactly as expected, inspect the upstream structure and adapt only the ingestion mechanics—not the experiment design. Document the change.

## Git and generated artifacts

- Keep raw datasets, model weights, checkpoints, large prediction dumps, temporary Colab files, credentials, and run caches out of Git.
- Commit small manifests, configs, final metrics, schemas, prompts, tests, paper source, and lightweight reproducibility artifacts where appropriate.
- Never commit Codex auth/session material, ChatGPT credentials, HF tokens, or any other secret.
- Keep `.gitignore` explicit and conservative.

## Documentation

The final repository must be reproducible by another person.

`README.md` should eventually contain:

- project purpose in plain language;
- exact setup instructions;
- dependency installation with `uv`;
- dataset-fetch/build commands;
- Codex prerequisite and teacher pilot/production commands;
- Colab CLI training workflow;
- evaluation and paper-asset commands;
- expected outputs and where they are written;
- important limitations, especially scoped ABSENT/UNKNOWN semantics, reentrancy-only generalization and compiler-era coverage, and incomplete project ancestry;
- current implementation/spec compatibility and required human review steps.

Do not over-document unfinished behavior. Keep README commands synchronized with the actual CLI.

## Paper support

The codebase should make the paper easy to write. Preserve machine-readable outputs that directly support the tables/figures defined in `SPEC.md`.

Do not fabricate results, fill missing metrics with placeholders that look real, or infer experimental outcomes before runs are complete. It is fine for the paper skeleton to contain clearly marked TODOs until actual results exist.

## Decision rule when something is unspecified

When `SPEC.md` does not specify an implementation detail:

1. choose the simplest reproducible option;
2. keep the experimental behavior unchanged;
3. prefer deterministic behavior;
4. make the choice explicit in code/config/docs if it affects reproducibility;
5. ask the user only when the choice would materially alter methodology, cost, external-resource use, or project scope.

## Definition of done

The project is done only when:

- the locked experiment can be reproduced from documented commands;
- automated tests for all declared invariants pass;
- data provenance, actual human label review, support/breadth gates, and split integrity are recorded in a frozen v2.2 dataset;
- teacher generation is isolated, validated, resumable, and auditable;
- both SFT conditions can be trained through the same reproducible Colab workflow;
- Base, Label-SFT, and Report-SFT can be evaluated deterministically;
- human-evaluation materials can be generated and scored without unblinding during rating;
- final tables/figures can be generated from real result files;
- README and paper source accurately describe the implementation;
- no unsupported claims are introduced beyond what the experiment actually measures.
