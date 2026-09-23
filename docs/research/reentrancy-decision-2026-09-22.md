# Reentrancy-only revision, September 22, 2026

The user approved narrowing the experiment to reentrancy after reviewing the
current evidence inventory and the value of a more focused NLP comparison.
SPEC v2.1 is authoritative. This document records the rationale; no model results
informed the change, and no teacher generation or training has been run.

## What changes

- One active family/check: REENTRANCY. PRESENT and scoped ABSENT remain targets;
  UNKNOWN remains evidence-ledger uncertainty, never a student output class.
- Binary macro-F1 replaces the multi-family score. Positive precision/recall,
  invalid outputs, group-bootstrap uncertainty and independent localization stay.
- The reviewed-test target retains 20 positives and 20 negatives for this task.
  Minimum group support remains 30/5/10 per polarity for train/validation/reviewed
  test. Removing redundant check-level gates does not lower those minimums.
- The blinded report comparison retains up to 25 queries. Per-cell teacher pilot
  and supervision-audit quotas stay unchanged: three and five per verdict,
  respectively, now totaling at most six pilot queries and ten audited reports.
- Active spec/config/record schema version is 2.1; the output namespace is
  `data/processed/reentrancy-v2.1/`. The subsequent user-authorized cleanup removed
  obsolete designs, implementations and generated copies. Current provenance and
  all approved raw evidence remain; incompatible formats are still rejected.

## What stays

All seven approved source pins and their development/external roles stay. All
native assessments survive, including non-target observations, but only
reentrancy creates active candidates. Protected raw contexts remain in leakage
checks even without a target label. Full-source inputs, native scopes, natural
imbalance, no synthetic victim-code examples, and group isolation stay.

The exact student, teacher, budgets and QLoRA settings stay. Base-Label,
Base-Report, Label-SFT and Report-SFT are evaluated on the same frozen test IDs;
both adapters train on identical accepted query IDs. Report targets are longer,
so differing completion-token exposure/compute must be reported. The comparison
does not isolate explanatory text under equal training-token exposure.

The narrower design improves focus and curation feasibility, particularly by
removing the unresolved broad authorization support requirement. It does not
guarantee better metrics, a powered test, or transfer to other vulnerabilities.
Grounding requires technically meaningful human assessment; fluency and JSON
validity alone cannot establish it.

## Modern code and possible future sources

Use the strongest compatible real-code evidence across compiler eras for the
main study, with a separately verified FORGE challenge. Compiler pragmas do not
date deployment, and narrowing the task does not add modern examples.

- [OWASP's data and methodology](https://scs.owasp.org/sctop10/data-sources/)
  does not support motivating reentrancy as the most frequent current attack.
  Its reported 2025 incident sample is led by business-logic and access-control
  issues; the Top 10 ordering is primarily practitioner-survey based.
- [Reentrancy Redux's authors' artifact](https://zenodo.org/records/15112729)
  describes 74 incidents from 2016–2024. It is a source of case leads, not 74
  ready-to-train victim-source records. Exact vulnerable versions and compatible
  source context would still need recovery and review.
- [Reentrancy Detection in the Age of LLMs](https://arxiv.org/html/2603.26497v1)
  reports a reverified aggregate of 432 contracts and 143 handcrafted scenarios.
  The aggregate mainly contains Solidity 0.4/0.5 sources and has CGT ancestry;
  it is not automatically new or independent data. The paper's prose class
  totals disagree with its table, and its linked repository was not verified
  during our research. Its threat model must be compared with ours before any
  adoption. Handcrafted scenarios remain outside this real-code baseline.

These resources are related work/research leads only. No extra datasets,
handcrafted diagnostic cohort, compiler execution pipeline, or exploit replay
framework were admitted by this revision.

## Reading the new counts correctly

Rebuilding the active taxonomy can change proposed polarities and connected
components. An inactive-property conflict no longer quarantines a reentrancy
candidate by itself. FORGE keyword matches also no longer create multiple
active-check candidates. Neither change is human adjudication or label
certification; unresolved reentrancy evidence remains quarantined.

See the [baseline dataset card](../data/reentrancy-baseline-v2.1.md) and its
machine-readable statistics for actual counts. Final semantic eligibility,
group splits, prescribed human reviews, support checks and freeze still precede
all resource-consuming model work.
