# Synthetic Audit Distillation — Project Specification

**Status:** REENTRANCY DESIGN LOCKED; v2.2 PROVISIONAL SPLIT BUILT, HUMAN REVIEW AND FREEZE PENDING  
**Version:** 2.2  
**Revised:** 2026-09-23, before any teacher generation, model training or human label review  
**Project type:** University NLP / Information Linguistics project  
**Working title:** *Synthetic Audit Distillation: Training a Small Language Model to Assess Reentrancy and Generate Grounded Reports*  
**Implementation:** Python 3.12, `uv`, normal Python modules and thin CLIs  
**Training environment:** Google Colab via the official Google Colab CLI  
**Report language:** English  
**Submission deadline:** 2026-09-30 23:59

---

# 1. Authority, revision, and implementation status

This file is the source of truth. The user approved the reentrancy-only revision
on September 22, 2026 to focus this university project on NLP: structured report
supervision, scoped verdict prediction, and code-grounded explanation quality.
Version 2.1 supersedes the earlier multi-family designs. The user subsequently
authorized removal of obsolete implementations, archives and generated outputs.
Keep the current protocol, source evidence, baseline provenance and concise
[revision rationale](docs/research/reentrancy-decision-2026-09-22.md).

**Version 2.2** (approved September 23, 2026, before any model result or human
review) changes: analysis-before-verdict reports; checkpoint selection by
validation macro-F1; CGT and the FORGE challenge inactive; a per-group query cap;
split-then-match 1:1 balanced cohorts; Salzano negative coverage confirmed at the
stratum level; and additional shortcut baselines and slices. The v2.1 inventory
is reused unchanged as the release input. Rationale:
[v2.2 revision](docs/research/revision-v2.2-2026-09-23.md).

Exactly one family and check, REENTRANCY, is active. PRESENT and scoped ABSENT
remain supervised labels; UNKNOWN remains ledger-only. Keep the seven pinned
corpora, native scopes, full-source context, evidence quality, clone/project
isolation, human review, Base/Label-SFT/Report-SFT comparison, and resource gates.
Teacher/student models, QLoRA hyperparameters and token budgets are unchanged.
No model results informed this revision. Narrowing does not establish higher
accuracy, greater statistical power, or modern-code coverage.

The active data CLI implements the v2.1 candidate inventory baseline and its
mechanical validation, not semantic certification or a frozen training release.
Final eligibility/adjudication, grouped development partitions, prescribed human
review and freeze remain required. Obsolete classifier/split/report code has
been removed; retained tests exercise the current implementation. Active commands
must reject incompatible config/schema/manifest versions and inactive checks.

This is an exploratory NLP experiment. A legitimate dataset has traceable labels,
explicit uncertainty, defensible held-out examples, and honest generalization
claims. No teacher generation or Colab training is allowed before Sections 10–13
pass; each real resource-consuming run still requires explicit run authorization.

Keep one student, two adapters, and no auditing platform. The ACL-format course
paper has at most eight content pages excluding references and covers motivation,
related work, methodology, implementation, evaluation, limitations and
reproducibility. Ordinary mechanics use the simplest deterministic implementation;
material protocol changes require a declared revision.

---

# 2. Research objective

Study whether synthetic structured explanations improve a small code language
model's ability to assess reentrancy in a specified Solidity code scope.
The code is real existing source; labels come from traceable upstream assessments
and the declared human review process. The teacher generates explanatory
supervision only. It does not create Solidity, establish evaluation truth, or
fill missing labels.

An input contains a canonical vulnerability check, its assessed file/contract/
function, the full supplied source file, and any necessary supported execution
assumptions. Label-SFT predicts `PRESENT` or `ABSENT`; Report-SFT predicts the same
verdict with a structured explanation. The check is supplied, the verdict is not.
This measures targeted assessment, not automatic discovery of an unrestricted
set of vulnerabilities, and not proof of exploitability on a live deployment.

---

# 3. Research questions

**RQ1:** Does report-supervised fine-tuning improve scoped reentrancy-verdict
prediction over the unmodified student? The format-matched comparison is
Report-SFT versus Base-Report on the same reviewed held-out queries.

**RQ2:** Does learning to write a grounded analysis *before* the verdict improve
verdict prediction compared with verdict-only fine-tuning, and how do both compare
with simple lexical/metadata baselines? Compare Report-SFT and Label-SFT using
identical accepted training and validation query IDs and identical evaluation
queries. Report different completion-token exposure and compute; this is not a
controlled equal-token ablation of explanatory text alone. Base-Label supplies
the label-format baseline.

**RQ3:** Are generated reports structurally valid, localized to independently
annotated evidence, and grounded in the supplied code? Use schema metrics,
independent localization annotations, and a blinded Base-Report/Report-SFT human
comparison. Do not equate agreement with teacher text with correctness.

The primary prediction metric is binary macro-F1 over PRESENT and ABSENT, defined
exactly in Section 26, with positive precision/recall and group-bootstrap uncertainty.
No measure is a generic claim of practical audit usefulness.

---

# 4. Hypotheses

- H1: Label-SFT improves verdict prediction over Base-Label.
- H2: Report-SFT improves verdict prediction and structured validity over Base-Report.
- H3 (open question): analysis-first Report-SFT may help the verdict by reasoning
  before deciding, or hurt it when a flawed analysis propagates. Either direction
  is a valid finding; report it with the paired interval.
- H4: Report-SFT improves human-rated grounding over Base-Report.

These are directional hypotheses. Negative or mixed results are valid. One
training seed and limited independent groups restrict conclusions about small
differences and training variability.

---

# 5. Scope

Include real-source supervised queries for the single REENTRANCY check;
partial annotations; a merged development corpus; grouped held-out evaluation;
a reviewed primary test subset; and SmartBugs external localization. The FORGE
modern challenge is inactive in v2.2 and reported as unavailable. Keep one student architecture,
Base/Label-SFT/Report-SFT weights, QLoRA, and a reproducible CLI workflow.

Exclude generated or injected vulnerable code from the primary corpus, scanner
votes as gold, automatic LLM relabeling, arbitrary source cropping, automatic
patch-based negatives, arbitrary whole-contract security claims, RAG, agent
frameworks, scanners or compilation as universal prerequisites, additional
student architectures, hyperparameter sweeps, product deployment, and BLEU/ROUGE
claims of technical correctness. Tiny synthetic fixtures remain valid for tests.

Access control, unchecked calls, arithmetic, and time manipulation are inactive.
Retain their native assessments for provenance and contamination references, not
training queries, derived negatives, or extra evaluation classes. Adding another
check, dependency-extracted contexts, handcrafted diagnostic corpora, or training
conditions requires another explicit revision. Reentrancy-only conclusions do
not demonstrate general vulnerability-detection competence.

---

# 6. Terminology

- **Source artifact:** an original source file at a pinned revision, with aliases.
- **Assessment:** an upstream or human judgment of a property at a stated scope.
- **Query:** one canonical check + scope + source context + execution assumptions.
- **Family:** REENTRANCY, the sole active reporting category; not a predicted label.
- **Check:** a precisely defined vulnerability question within a family.
- **PRESENT / ABSENT:** vulnerability present/absent for that check and scope under
  the stated assumptions. Neither label describes all of the source's security.
- **UNKNOWN:** missing, inapplicable, insufficient, or unresolved evidence in the
  annotation ledger. It never becomes a supervised target or a scored negative.
- **Group:** a connected component of known project, version, and clone links.
  Incompletely known projects must not be described as verified independent DApps.
- **Upstream-reviewed:** upstream documents human assessment; not independently
  certified by this project. **Locally reviewed:** the declared human review was
  completed, with an inspectable record. Neither term means infallible truth.
- **Teacher:** GPT-5.6 Sol through Codex CLI, generating explanatory targets.
- **Student:** Qwen2.5-Coder-1.5B-Instruct; **Label-SFT** and **Report-SFT** are its
  two adapters. **Base-Label / Base-Report** are two prompts for one base model.

`NONE` is retired as a vulnerability/verdict class. It remains the required
severity value for ABSENT reports and may occur in original upstream metadata
or legacy artifacts, never as an inferred whole-file security guarantee.

---

# 7. Taxonomy, checks, and threat model

Exactly one family and one primary check are active:

| Family | Check ID | Question being assessed | Evaluation role |
| --- | --- | --- | --- |
| `REENTRANCY` | `REENTRANCY` | Can an untrusted external call enable re-entry that violates asset/accounting state invariants before the relevant operation is safely finalized? | Primary |

Maintain the versioned `configs/taxonomy.yaml` definition and native-property
candidate mappings. SWC-107, RE, and reentrancy names select candidates; they do
not prove semantic equivalence. Merely calling out before a state update is
insufficient evidence. Native negatives require the same check, scope and
supported assumptions. Non-target findings never imply reentrancy absence.

Assess single-function or cross-function behavior only when the full supplied
source and supported assumptions suffice. Keep read-only reentrancy,
oracle/economic manipulation, and unsupported cross-protocol behavior out of
scope. Do not broaden the definition to admit a newer incident. Imported guards,
inheritance, callbacks and deployment state cannot be invented; missing decisive
context makes a judgment UNKNOWN.

Assume an untrusted caller/callee and uncompromised legitimate privileged
principals. Preserve compiler constraints and verified execution context when
relevant, equally for teacher and student. A Solidity pragma alone establishes
neither an EVM fork nor the code's deployment/collection date. Do not choose
historical assumptions merely to retain a positive.

Preserve supported challenging negatives (for example, reviewed external calls
with effective state ordering or guards). A `nonReentrant` name is not proof of
protection, and its absence is not proof of vulnerability. Describe the causal
mechanism and evidence in report evaluation; fluent templates are insufficient.
Native observations outside REENTRANCY remain in the evidence ledger, with no
active candidate mapping. Conflicts compare compatible reentrancy judgments;
inactive-property disagreements do not become reentrancy contradictions.

---

# 8. Approved sources, pins, and evidence roles

Only the following snapshots are approved. Record original collection ancestry,
not merely the name of the repackaging repository. Do not sum headline dataset
sizes as if they were new independent contracts.

| Source and reference | Pinned revision | Role |
| --- | --- | --- |
| [DAppSCAN-source](https://github.com/InPlusLab/DAppSCAN) | `66a56619c44770e05c2db600fa6468115ff0dcd5` | Development, audit-derived positives |
| [SCRUBD-CD](https://github.com/sujeetc/SCRUBD) | `9dba1928d4aea9a5d27014e5f31a8ed0b703f711` | Development, native function judgments; SD excluded |
| [Salzano et al.](https://github.com/fsalzano/Empirical-Analysis-of-Vulnerability-Detection-Tools-for-Solidity-Smart-Contracts) | `da079440bf2cf4fd803c864ef29aeea8a3da50c3` | Development, corrected manual annotations; curated SmartBugs portion external only |
| [CGT](https://github.com/gsalzer/cgt) | `f8cd72cf7fbbfebc809c454667eee271706a4b2b` | Development, selected real-code original collections |
| [ScBench](https://github.com/blockchain-security-artifacts/sc-developer-study-1) | `840d5fadd392f4777045fa1af3299fd903e9c6bf` | Development, native property judgments |
| [SmartBugs Curated](https://github.com/smartbugs/smartbugs-curated) | `230e649123477eff332742a59a1c7cc6dc286cab` | Protected external positive/localization benchmark |
| [FORGE-Curated](https://github.com/shenyimings/FORGE-Curated) | `a6b8506343184045074909e6619a67a44da4b1a5` | Verification queue for a separate modern audit challenge; never development |

CGT originals allowed for screening: CodeSmells, ContractFuzzer, Doublade, eThor,
EthRacer, EverEvolvingG, NPChecker, Zeus. Exclude SolidiFI, JiuZhou,
NotSoSmartC, SWCregistry, and SBcurated from development. Eligibility still
requires documented human assessment, real-code origin, and compatible semantics;
an allowed collection is not blanket permission to ingest tool outputs. CGT may
repair/recover sources and preserves named-contract scope; its native line
coordinates and property meanings cannot be assumed to match another corpus.
[CGT metadata](https://github.com/gsalzer/cgt).

Use SCRUBD's pinned CD `labels.csv`, not scanner-result CSVs; blank cells mean
unknown, and names must resolve to actual declarations. Preserve student-review
provenance and analyzer-based selection bias. Use Salzano's corrected manual
labels, not the original `zeus_safe`/`zeus_vulnerable` collection name as the
verdict. Retain line annotations only if matched to the exact supplied source.
[SCRUBD paper](https://arxiv.org/abs/2412.09935),
[Salzano paper](https://arxiv.org/abs/2505.15756).

ScBench's rows assess particular properties; repeated deployment addresses or
source files across CSVs are not independent contracts. The filenames encode
labels and must never enter model prompts. Preserve source modifications and
compiler/deployment metadata. Non-reentrancy properties remain inventory-only.
[ScBench paper](https://sanadlab.org/assets/pdf/TamerMSR2026.pdf).

FORGE tags and keyword matches are candidate selectors. A human must verify the
original report, precise audited pre-fix revision, actual finding semantics,
supplied code sufficiency, and location mapping. Drop informational non-bugs,
resolved/fixed-only versions, unavailable exact revisions, and unsupported
multi-file context. Never treat the nearest available commit as the audited one.
FORGE states that mapping review is ongoing and some source revisions differ.
[FORGE documentation](https://github.com/shenyimings/FORGE-Curated).
Freeze this challenge before model runs; if none qualify, report that explicitly
and omit its metrics. It cannot repair inadequate primary reentrancy support.

Fetch only needed pinned sources/metadata; inspect complete subtrees rather than
trusting truncated GitHub recursive trees. Verify content checksums, record URLs,
revisions, annotation paths/hashes, extraction mechanics, dates, and upstream
license notices. A repository's code license does not automatically cover every
included Solidity file. Keep raw code/reports local and gitignored; publish
manifests, transformations, and fetch instructions. Do not acquire gated data or
accept account-sharing terms as an automatic part of the build.

**v2.2 active sources.** Development evidence comes only from upstream-reviewed
DAppSCAN, SCRUBD-CD, Salzano and ScBench assessments. CGT stays ingested and
UNVERIFIED (inventory and contamination reference only). FORGE stays ingested and
reserved; its challenge is unavailable in v2.2. SmartBugs remains protected external.

The main development corpus may span compiler eras. Do not restrict it to modern
Solidity at the cost of unsupported labels or inadequate positive support.
Modern transfer is a separate, bounded FORGE challenge, with unavailable results
reported honestly if verification fails. Keep source era and collection bias
visible in all counts; a new publication is not necessarily new code.

Reentrancy Redux, the 2026 Reentrancy Detection in the Age of LLMs benchmark, and
incident/PoC repositories are research leads only. They are not approved additions
to this baseline: exact artifacts, real-code origin, licensing, overlap,
threat-model compatibility and source/label alignment must be reviewed before a
separate source-admission revision. Handcrafted attacks and PoC harnesses do not
become real victim-source training examples. No new source pin is inferred from
the user's approval to narrow the current experiment.

The current baseline must be rebuilt from pinned inputs, not inferred from
superseded feasibility estimates or presented as reviewed/frozen data. The
current dataset card and small reproducibility manifests retain its evidence.

---

# 9. Query unit, context, and record model

## 9.1 Query scope and full-source context

One supervised example is one known check verdict for one explicitly identified
scope. Scope is FILE, CONTRACT (qualified declaration), or FUNCTION (contract plus
full signature, including constructor/fallback/receive distinctions). Store exact
declaration token spans and original line spans. Use a pinned parser or verified
unambiguous resolution; unresolved overloads, inheritance, or same-name ambiguity
are excluded with reasons, never guessed by first match.

Supply the **complete original source file with comments blanked**, even for a
function query. Do not pass isolated function bodies or vulnerability-centered
windows. Contract scope covers that contract's behavior, function scope covers
execution initiated through that function including relevant calls/modifiers,
and file scope covers the declared file task. Scope boundaries are not gold
vulnerable-line annotations. Never select a narrow positive scope from gold lines
while presenting negatives at whole-file scope.

Relevant state, modifiers, inherited guards, and internal call definitions must
be present when necessary to decide the label. Unrelated unused imports need not
be bundled. When missing imports/context determine the verdict, mark UNKNOWN.
No automatic flattening, snippet extraction, or multi-file bundles are introduced
in v2.1. This deliberately bounds engineering and preserves source coordinates.

## 9.2 Sanitization, identities, and model input

Blank all comments uniformly across every corpus, preserving source length and
all CR/LF positions; preserve quoted literals and executable tokens. Render
one-based lines as `0001 | ...`; a final terminator creates no phantom line.
Keep original raw-source and vulnerable-line metadata separately. Never include
dataset name, original path/address/filename, upstream verdict, SWC/CWE label,
audit title/prose, annotation comments, finding lines, reviewer decisions, or
source quality tier in student input. Required code literals remain code.

The shared semantic input is a canonical payload containing `check_id`, its fixed
definition, resolved scope, supported execution assumptions, and numbered source.
Both SFT conditions receive that identical payload. Output-format instructions
are versioned separately. The teacher additionally receives the known verdict.

Retain `raw_sha256`, normalized-source `code_sha256`, and lexical
`code_identity_sha256`: normalized hash uses LF, trims trailing
whitespace and empty edge lines without Unicode normalization; lexical identity
hashes the compact JSON token-spelling array, ignoring comments/layout only.
Preserve identifiers, literal contents/spellings, operators, and token boundaries.
These hashes never rewrite model input. Add `source_input_sha256` for exact
numbered source and define v2.1 `model_input_sha256` over the exact canonical shared
payload, including check/scope/assumptions. Cache identity must also include the
task prompt, verdict, and generation settings. Version these algorithms.

## 9.3 Budgets

Student/tokenizer: `Qwen/Qwen2.5-Coder-1.5B-Instruct`, revision
`2e1fd397ee46e1388853d2af2c993145b0f1098a`. Count full numbered code without special
tokens: maximum **6000**. Exclude longer sources and record counts; never truncate.
Maximum complete chat-template sequence is **8192** tokens for both conditions,
including all prompts, completion, and termination tokens. Teacher semantic
reports must fit **480** student tokens in canonical compact JSON; inference
retains **512** new tokens. Reject over-budget reports through the retry rules,
not shortening or repair. The report acceptance cap does not discard student
predictions that otherwise satisfy inference/schema rules.

Canonical JSON uses schema field order, UTF-8 without ASCII escaping, compact
separators, and no surrounding whitespace. Validate both complete SFT sequences
before the shared cohort freezes. An overlength/missing teacher target excludes
that query from both training conditions.

## 9.4 Persisted layers

Keep simple typed records and inspectable JSONL/Parquet; no database:

- **Artifacts/aliases:** original source/revision/path, hashes, compiler context,
  deployment/repository links, origin collection, license and extraction metadata.
- **Assessment ledger:** native record/property/polarity/scope, canonical check,
  PRESENT/ABSENT/UNKNOWN, evidence kind/reference, coverage assumptions, any
  derivation, independent lines and coordinate provenance, review status/reason.
- **Queries:** canonical payload and `query_id`, all supporting assessment IDs,
  resolved scope, group ID, split, verdict, eligibility and exclusion reasons.
- **Review/group/freeze manifests:** decisions, grouping edges, source counts,
  fixed queues, effective settings, artifact hashes, and protocol versions.

Query identity uses lexical source identity + resolved scope token identity +
check + normalized assumptions. Repeated supporting assessments do not create
duplicate queries. Multiple distinct reentrancy scopes in one source are allowed
but always share a group/split. Report source files, queries, deployments, known
projects, and groups separately.

---

# 10. Admission, negative evidence, conflicts, and review

## 10.1 Eligibility

Admit only non-empty readable/lexable real-source artifacts with exact annotation
links, compatible check definitions, resolvable scope, sufficient context,
supported semantic assumptions, and the Section 9 budget. Keep multi-SWC and
multi-vulnerability files; create only their known compatible queries. Preserve
non-target findings as provenance; their presence alone supplies no target label.

Evidence states are `UPSTREAM_REVIEWED`, `LOCALLY_REVIEWED`, and `UNVERIFIED`.
The first requires a documented upstream human-review protocol and a traceable
assessment, not a dataset's name or marketing description. Unverified, tool-only,
LLM-only, synthetic/injected, and unresolved records remain inventory/queues and
never enter either SFT condition or primary evaluation. Local manual review means
a human reviewer signing an inspectable decision; an assistant may prepare cards
but must not impersonate a human review or automatically certify a label.

## 10.2 Negative evidence

ABSENT requires an explicit reviewed negative for the same check, scope, and
assumptions, or documented comprehensive assessment coverage that entails it.
Record the exact evidence/derivation. In particular:

- DAppSCAN files without SWC annotations are UNKNOWN, not negatives.
- Empty/missing source labels, parser failures, and tool silence are UNKNOWN.
- A negative function is not a negative contract/file.
- A negative assessment of another weakness is not a reentrancy negative.
- A Salzano explicit no-finding record may support one reentrancy query only
  after confirming that the manual annotation protocol covered reentrancy over
  that supplied file. No derivation from its old collection name is allowed.
  v2.2 confirms this at the stratum level from the published protocol (every
  instance annotated against all DASP Top-10 categories; every not-vulnerable
  judgment double-validated; consensus on all conflicts). The declaration lives in
  `configs/release.yaml`; the training-label audit still checks sampled cards.
- Do not manufacture negatives by swapping class names, using another class's
  positive label alone as negative evidence, assuming post-fix code is safe, or
  editing guards in code. Explicit reviewed cross-check coverage remains usable.

Do not multiply negative queries or broaden their scopes. Preserve challenging
reviewed negatives as well as simpler ones (balanced later only by Section 13
matching), with no
unsupported guard-based labels or manually manufactured fixes.

## 10.3 Conflict policy

Compare assessments at compatible scope/check/assumptions before splitting and
before any positive/negative sampling. Different scopes or unassessed properties
are not conflicts. A broad/file negative can conflict with a supported narrower
positive; positive membership alone does not prove a particular subtype.
Different compiler/EVM/initial-state interpretations require resolution, not votes.

Keep all evidence. Quarantine all queries for an identity with an unresolved real
contradiction; never majority-vote correlated sources, prefer whichever label
helps balance, or silently select a dataset as authoritative. A human may resolve
it before freezing using original evidence and a recorded rationale. Corrections
apply consistently to all aliases/affected records. No test predictions may be
used for adjudication. Unknown/withdrawn judgments are excluded and counted.

## 10.4 Training-label quality audit

After provisional group assignment, sample up to five unique training groups per
original-collection/check/verdict cell, with at most 120 total review cards.
Round-robin sorted nonempty cells, selecting from sorted IDs with seed 42 and no
replacement; cover every active cell at least once before allocating second
slots. If 120 cannot cover every cell, report the additional required review
instead of treating unreviewed cells as audited. Review the source-to-label link,
check equivalence, scope, context, and semantic assumptions.
Publish denominators, errors, unresolved cases, and reviewer identity. One human
rater is sufficient for this exploratory study; an independent second rater is
welcome but not assumed available.

Resolve each sampled issue. A systematic mapping, source-version, or coverage
error requires fixing/quarantining the entire affected stratum and rebuilding,
not deleting just the sampled failures. Isolated unresolved identities stay
quarantined. This sample estimates residual risk; it does not certify every
upstream-reviewed training label. Reviewers do not read model predictions.

## 10.5 Reviewed primary test

Reserve groups first (Section 12), then create deterministic review queues from
the held-out partition. Retain the per-task target of **20 PRESENT and 20 ABSENT
reentrancy queries**, at most **40 final queries**. Within each polarity,
round-robin original collections in sorted order; within a cell use seed 42 over
sorted IDs. Allow at most one query per group/polarity. The
same group may support different cells; uncertainty still clusters by group.
Review candidates in that fixed order; preserve the full queue and every outcome.

For each card, the human first sees sanitized source, the check, scope, and
assumptions and records an initial verdict/unknown before revealing the upstream
verdict/evidence. Then reconcile with original assessment/audit evidence and
record the final verdict, rationale, version/context checks, and independent
location evidence when available. Do not invent line-level gold from a function
name. The rater is blind to future model outputs; do not claim independence from
upstream evidence after that evidence is revealed.

A corrected verdict joins its final-polarity queue; ambiguous items are excluded
with reasons. Continue only within the reserved held-out groups until quotas or
available candidates are exhausted. Final selection is the earliest eligible
reviewed items under this ordering, with a logged group-conflict tie-break.
Never move held-out groups into training or selectively replace difficult items.
Publish shortfalls and the support gates below. Other held-out upstream-reviewed
queries form a secondary test, never a substitute for the primary review.

Human label review is distinct from the later teacher-quality audit and final
blinded report-quality rating. Finish it and freeze labels before model runs;
keep test evidence unavailable to teacher/prompt development.

---

# 11. Deduplication and leakage groups

Build the raw evidence/identity index across **all readable approved raw corpora**
before class/length filtering or query sampling. Include excluded aliases and
non-target SmartBugs artifacts as contamination references. Invalid/unlexable
files get explicit exclusions rather than guessed fingerprints. Activate split
grouping over candidate model contexts and protected assessed contexts after
eligibility resolution, before splitting or review sampling. Retain raw aliases
for conflict/contamination checks even when the alias itself cannot be admitted.

A shared vendored/library file that occurs in neither selected model context is
not evidence that two unrelated projects are the same project. Such inventory
matches must not create giant components through unused dependencies. If shared
code actually occurs in an assessed/model context, apply the clone rules below;
do not exempt it merely because its origin is a common library. Record inactive
raw matches and the context-based reason for not activating a split edge.

Merge exact lexical-source aliases, but retain their provenance and distinct
compatible assessments. Prefer a representative with verified independent line
metadata, then lexicographic `(source_id, revision, path, native_id)` order.
Coalesce equivalent queries rather than erasing all but one file-level label.
Coordinates remain those of the selected source; transfer other coordinates
only through a verified token map, never by copying line numbers blindly.

Create group edges for:

1. Known canonical project/repository identity, audit aliases, shared deployment
   identity, implementation/proxy/version links when established, and same-code
   aliases. Merge repository links transitively; do not fuzzy-match project names.
2. Exact full-source token skeletons: retain Solidity keywords, type names and
   operators; consistently rename other identifiers by first occurrence within
   the compared unit; replace numeric and quoted literals by distinct type
   markers. Remove pragma statements only for this grouping comparison. Specify
   and test the complete token/keyword rules under a pinned version. These are
   grouping heuristics, never label identities or rewritten model inputs.
3. Exact normalized clones of assessed functions of at least 50 tokens, compared
   against declarations across the inventory. Trivial signatures/getters alone
   do not connect otherwise unrelated projects.
4. Near-clone source/assessed-contract skeletons of at least 100 tokens with token
   length ratio >= 0.8 and set-Jaccard similarity of token 5-grams >= 0.85. Verify
   every edge exactly; candidate indexing must not silently miss qualifying
   pairs. Match whole source/assessed contracts, not just a shared unused library.

Version the tokenizer, skeleton rules, thresholds, resolution, and edge reasons.
Connected components define indivisible split groups. Small-function cases with
unresolved provenance/clone risk require review before primary-test eligibility.
Do not break a large component or raise thresholds to obtain prettier class
counts. Report largest groups, clone concentration, and excluded/unknown links.

Any component touching SmartBugs is protected external: none of its members may
enter development. Any component touching FORGE is held out for the modern
challenge unless already SmartBugs-protected; score it in at most one external
cohort. Development aliases in protected components are excluded, not extra
independent external observations. Keep external label disputes quarantined.

Assert zero exact source/hash/query/group overlap between partitions and zero
**known** project overlap. For unresolved project ancestry report clone-grouped
generalization, not verified project-disjoint generalization. Clone-group hashes are
not semantic-equivalence proofs. Save all edges and a residual provenance/clone
risk report; public pretraining exposure remains an uneliminated limitation.
Primary and secondary test lists are views within one held-out partition; their
query IDs differ but their source/group IDs may coincide.

---

# 12. Split, support gates, and freeze

After protected-component exclusion and the Section 13 group cap, split
development groups once, targeting 5/7 training, 1/7 validation, and 1/7
held-out. Use StratifiedGroupKFold with seven folds on query strata
`(original collection, verdict)`, shuffle=True; fold 0 is held-out, fold 1
validation. Groups are the inventory's connected components, a conservative
superset of edges among the eligible contexts. Then apply Section 13 matching
inside each partition. Try seeds 42 through 1041 and choose the first whose
*matched* partitions satisfy the pre-review support and breadth rules and give the
held-out fold at least 20 distinct groups per polarity (the reviewed target).
Record every attempt's support summary and the chosen seed. Count distinct
supporting groups, not repeated file/query rows.

Required minimum support after review and after shared-cohort rejection:

| Unit | Train groups per polarity | Validation groups per polarity | Reviewed primary test groups per polarity |
| --- | ---: | ---: | ---: |
| REENTRANCY | 30 | 5 | 10 |

The reviewed test target is 20 per polarity; these lower gates allow
documented scarcity, not class removal. For pre-review splitting, use eligible
upstream counts as provisional support and require the corresponding held-out
minimums. Retest with actual reviewed/accepted counts before freeze/generation
and before training; do not choose new seeds in response to model performance.
If later exclusions break a gate, stop and surface the feasibility problem.

For each primary check, at least one original collection must contribute both
polarities to train, validation, and reviewed test. Record original-collection x
check x polarity x scope and compiler-era distributions. Report additional
single-polarity sources separately. If source membership perfectly determines
polarity for a primary check, its pooled metric cannot satisfy the gate.

These are operational minimums, **not a statistical power calculation**. Show
actual independent-group counts and uncertainty. No claim of a reliable small
gain follows from passing them; failure must not silently weaken the evidence
requirements, change the threat model, or redefine the benchmark.

Freeze before the teacher pilot: artifact/assessment/query IDs, source pins,
checks/definitions, polarity/coverage rules, supported assumptions, groups,
partition assignments, review records, primary/secondary/external memberships,
sample queues, and independent location sets. Hash a `dataset_freeze.json` and
version its dependent files. Runtime timestamps are provenance; deterministic
content hashes must exclude volatile timestamp fields.

Teacher prompts use training examples only. Validation is for within-condition
checkpoint selection; all held-out data is forbidden for prompt, taxonomy,
preprocessing, and hyperparameter tuning. After any model results, discovered
label errors are reported against the frozen benchmark; a corrected release and
rescoring must be clearly separate, not a rewritten primary result.

---

# 13. Maximize eligible data without manufacturing evidence

**v2.2 balanced matched cohorts.** The eligible pool is imbalanced (about 1:3.7)
and its scope kind and pragma predict the label. Therefore:

1. Keep at most **3 queries per group and polarity** (seeded hash order). Many
   functions of one project are not independent evidence.
2. After the Section 12 split, pair **every PRESENT query with one ABSENT control
   in the same partition** (1:1). Match keys are tried in order across all cases:
   (collection, scope kind, first-pragma minor) → (collection, scope kind) →
   (scope kind, pragma) → (scope kind) → any. Within a level prefer controls from
   not-yet-used groups, then seeded hash order.
3. Unmatched controls are excluded as `balancing_surplus` and recorded. Nothing is
   relabeled, oversampled, synthesized or turned into a pseudo-negative.
4. Report match levels, surplus counts and the remaining collection/pragma cues.
   Balanced held-out metrics do not estimate deployment prevalence.

Inactive checks never enter the supervised cohort. Train both adapters on the
same query IDs, order/seed, and three epochs. Repeated contexts across functions are not additional independent
contracts. Report queries per source/group and token exposure so large projects
or collections cannot be mistaken for broad coverage. Do not create multiple
paraphrased questions for one assessment to inflate dataset size.

All known-label data is finite and resource estimates use the actual frozen
query count. If the proposed teacher or GPU run exceeds available resources,
present the concrete counts/cost-in-usage and obtain a revised run plan; do not
silently discard examples or launch generation. Maximal eligibility does
not authorize unlimited subscription or GPU consumption.

---

# 14. Teacher model and annotation interface

## Locked teacher

**Teacher tier:** GPT-5.6 Sol  
**Codex model argument:** `gpt-5.6`  
**Reasoning effort:** `medium`  
**Interface:** Codex CLI (`codex exec`) authenticated with the user's ChatGPT subscription

Do **not** use the OpenAI API for the normal annotation workflow. The project intentionally uses the included Codex allowance to avoid incremental API spend.

The `gpt-5.6` Codex model selection resolves to the GPT-5.6 Sol tier. Medium reasoning is locked because this is a security/code-understanding annotation task where we want stronger reasoning than `low`, while still keeping subscription usage materially below `high`/`xhigh`/`max`.

Use a configuration setting for the model/reasoning values rather than scattering them through the codebase.

Record at least the following for every generation run:

- configured Codex model argument;
- teacher tier name used in the paper (`GPT-5.6 Sol`);
- reasoning effort;
- exact Codex CLI version;
- teacher prompt version/hash;
- schema version/hash;
- generation timestamp;
- Codex token-usage data when emitted by the CLI.

## Locked Codex generation settings

```yaml
teacher_backend: codex_cli
teacher_model: gpt-5.6
teacher_tier: gpt-5.6-sol
teacher_reasoning_effort: medium
teacher_model_verbosity: low
teacher_batch_size: 5
teacher_max_attempts: 2   # initial attempt + at most one retry
teacher_ephemeral: true
teacher_sandbox: read-only
teacher_approval_policy: never
teacher_ignore_user_config: true
teacher_ignore_rules: true
```

The annotation runner must invoke Codex non-interactively with the equivalent of:

```bash
codex exec \
  --model gpt-5.6 \
  -c model_reasoning_effort="medium" \
  -c model_verbosity="low" \
  --ephemeral \
  --sandbox read-only \
  --ask-for-approval never \
  --ignore-user-config \
  --ignore-rules \
  --output-schema <batch-schema.json> \
  --json \
  -o <output.json> \
  -
```

The exact flag spelling may be adjusted only to match the installed Codex CLI version. The effective settings above must remain unchanged.

Pin Codex CLI **0.154.0** for the initial implementation; incompatible installed
versions must fail preflight until explicitly reviewed. Run from a new empty
temporary directory with the full task on stdin. An empty directory and a
read-only sandbox alone are **not proof of isolation**: read-only still permits
reads and tool execution.

The runner must disable shell/file tools, web search, MCP/connectors, skills,
subagents, and inherited user/project instructions, and enforce a restricted
filesystem view that excludes the repository, audit reports, and unrelated local
files. Permit only runtime resources and invocation inputs/outputs. Authentication
and the CLI's model-service connection are host responsibilities, not additional
information sources available to the teacher. Agent network/tool access remains
disabled. No model or CLI substitution and no API fallback are allowed.

Before an authorized pilot, local isolation tests must demonstrate denied access
to sentinel files outside the allowed view and disabled external/tool facilities.
Record CLI version, effective isolation settings, and test evidence. If the
installed CLI cannot enforce these boundaries, stop and report the blocker rather
than relying on prompt instructions. During the approved pilot, verify actual
schema support and event logs; reject any invocation that used prohibited tools.

## Teacher information boundary

Only after dataset freeze and explicit approval for the run, give the teacher:
opaque sample IDs, the same canonical check/scope/assumptions and numbered source
as the student, the known PRESENT/ABSENT verdict, and annotation/schema rules.
Do not give source names, audit reports, reviewer rationales, independent gold
lines, held-out examples, or repository context. The teacher explains a known
verdict; it is not the source of that verdict.

For ABSENT, require a bounded explanation about this check and scope only, without
inventing global security. If the known label cannot be supported or context is
insufficient, the teacher must return the transport-level UNSUPPORTED outcome
defined below instead of inventing an explanation. This never relabels data.
The prompt must prohibit tools; enforced isolation remains mandatory.

---

# 14A. Teacher efficiency, pilot, and resumability

Codex subscription allowance is limited. No teacher calls occur during a normal
build, dry run, or tests. Before the real pilot or production run, show the exact
command, query/batch counts, and estimated input/output usage, then wait for the
user's explicit approval for that run. No automatic API fallback is permitted.

Batch up to **five queries per invocation**, final partial batches allowed;
concurrency **one**. Include each query once with one output per opaque ID.
For queries sharing a source within a batch, a source table referenced by opaque
IDs may avoid repeating identical code, provided every query gets the same full
context and semantics. Never use class-bearing filenames/IDs or duplicate examples
to fill a batch. Record actual serialized batch hashes and input-token estimates.

Generate only frozen development **train and validation** targets. Never generate
targets for the reviewed/secondary test, SmartBugs, FORGE, or label-only outputs.
Pilot selection is up to three training queries per primary-check/verdict cell,
without replacement, seed 42: **at most six queries**, at most two first-pass
invocations. Prefer distinct groups within a cell. Freeze prompts after inspecting
every pilot output; no test content may influence this process. Reuse valid pilot
work only when its complete generation identity matches the frozen protocol.

Use at most two attempts for a failed query: initial plus one retry. After a
structurally trustworthy batch, persist each valid item immediately, retain all
successful items, and re-batch only mechanically invalid/missing outputs. A
declared UNSUPPORTED result is a terminal rejection, not an invitation to pressure
the teacher into agreeing on a retry. Malformed batch JSON or ambiguous/duplicate
IDs invalidate the batch map; log why. No manual cherry-picking of valid reports.

Cache identity includes exact v2.1 model-input hash, known verdict, check-definition
version/hash, teacher model/reasoning settings, teacher prompt hash, semantic and
transport schema hashes, and effective isolation/CLI protocol version. Record
dataset freeze provenance separately; a different dataset filename alone is not
reason to regenerate identical valid work. Changed scope, assumptions, line
coordinates, or definitions must invalidate affected cache entries.

Support a zero-call dry run showing completed/pending/rejected query counts by
check/verdict/source, batch capacity, first-pass and maximum retry invocations,
actual serialized input estimates, bounded output estimates, and group coverage.
Report the expanded query count, not just distinct source files. Store
`runs/teacher/<run-id>/usage.json` with CLI version, invocation/retry counts,
requested/accepted/unsupported/rejected items, and input/cached/output/reasoning
tokens where emitted by `codex exec --json`. Missing usage is null, not zero.

Stop cleanly on subscription exhaustion, retaining completed work for resumption.
Do not launch an API or another teacher model. Any later exception needs a
separate explicit spec revision and run authorization.

---

# 15. Teacher prompt development

Develop the prompt only on the deterministic training pilot from Section 14A.
Inspect every output for schema behavior, appropriate scoped negatives, grounded
positive reports, and sensible UNSUPPORTED handling. Any pilot regeneration with
a changed prompt consumes allowance and needs an authorized run budget.

Freeze versioned teacher and student prompts/check definitions before production
generation. Prompts live under `configs/prompts/`; filenames/schema versions
must identify the current protocol. No hidden chain-of-thought requests, tools,
few-shot test examples, or reference-audit prose. Record final prompt hashes.
If pilot failures expose a dataset problem, follow the evidence/review protocol
and issue a new freeze before continuing, not ad hoc teacher-based relabeling.

---

# 16. Structured schema, version 2.1

The schema is an experimental operational schema, not an industry standard.
`schemas/v2.1/audit_report.schema.json` defines the semantic report; the transport
schema separately wraps up to five teacher results. V1 vulnerability labels are
not accepted by v2.1. The category/check is input metadata and is not scored as an
output the model supposedly discovered.

The v2.2 semantic report lives in `schemas/v2.2/audit_report.schema.json`.
Semantic PRESENT example (illustrative coordinates, not an experimental result):

```json
{
  "analysis": "Line 42 sends ether with call.value before line 47 zeroes the balance; no guard applies, so a re-entering callee can withdraw repeatedly.",
  "verdict": "PRESENT",
  "severity": "HIGH",
  "location": {"start_line": 42, "end_line": 47, "function": "withdraw"},
  "exploit_scenario": "A plausible consequence under the stated assumptions.",
  "recommendation": "A mitigation addressing the identified behavior."
}
```

Field order is part of the protocol: `analysis` comes first so greedy decoding
writes the analysis before committing to a verdict. Canonical JSON follows this
schema order.

- `analysis`: nonempty string, maximum 1,200 characters. It walks through the
  evidence in a fixed order — external calls, state reads/writes around them,
  guards or ordering that prevent re-entry — citing line numbers, and states the
  conclusion only in its final sentence. ABSENT analyses are limited to the
  requested check/scope/assumptions.
- `verdict`: exactly PRESENT or ABSENT; UNKNOWN is ledger-only.
- `severity`: NONE, LOW, MEDIUM, HIGH, CRITICAL. PRESENT requires a positive
  severity; ABSENT requires NONE. Severity is generated, not objective gold.
- `location`: PRESENT requires start/end integer lines, 1 <= start <= end <=
  source line count; `function` is an identifiable name or null. Supporting
  evidence may lie in a relevant helper/modifier outside a queried function's
  own lines, but within supplied code. ABSENT requires null. Automatic bounds
  validation does not prove semantic relevance.
- `exploit_scenario`, `recommendation`: nonempty strings of at most 900 characters
  for PRESENT, null for ABSENT; normally 1–3 sentences each.
- Strict types, all fields required, additional properties forbidden, duplicate
  JSON keys rejected, no coercion of booleans to line integers or strings to enums.
  The combined compact report also obeys the 480-token teacher cap.

Teacher transport:

```json
{
  "annotations": [
    {"sample_id": "opaque-id", "status": "OK", "report": {}, "reason_code": null}
  ]
}
```

Here `{}` is a schematic placeholder for a complete valid semantic report, not
a valid OK report. OK requires that report and a null reason. UNSUPPORTED requires
a null report and one of LABEL_NOT_SUPPORTED, INSUFFICIENT_CONTEXT, or
UNRESOLVED_ASSUMPTIONS. No alternative verdict/report is accepted as a correction.
Use a discriminated transport schema; opaque IDs and statuses are never student
targets. Require each requested ID exactly once and no unknown IDs.

Validate batch JSON/ID mapping first and reports per item next, so an individual
report failure does not discard other unambiguously mapped valid reports. Use
the strict schema for CLI output constraints as well as local semantic checks.

---

# 17. Teacher records and shared cohort validation

Persist append-safe JSONL records containing query/assessment/group IDs, source
aliases, split/freeze hash, exact input hashes, check/scope/assumptions, known
verdict, semantic report or unsupported reason, prompt/schema/model/CLI/isolation
versions, timestamps, attempts, validation results, and available usage.

Accept an OK report only if the transport map is trustworthy, the semantic schema
and contextual bounds pass, verdict equals the supplied known verdict, required
fields are present, target token cap passes, and the invocation used no prohibited
tools. Schema-valid fiction is still possible; automatic acceptance is not expert
verification. Reject/record UNSUPPORTED without changing the reference label.

After final attempts and full chat-template checks, reject a query from **both**
SFT conditions if its report is missing, rejected, unsupported, or over budget,
or if either condition exceeds 8192 total tokens. No replacement, negative
rebalancing, or taking test data. Freeze sorted identical accepted train/validation
IDs, input/report hashes, both sequence lengths, and prompt/template/tokenizer
versions in `shared_cohort.json`. Training verifies this manifest.

Recheck Section 12 training/validation support and source-polarity gates on that
accepted cohort. If they fail, report the issue before training. Report rejection
and unsupported rates by check, verdict, original collection, scope, and group.
The comparison is conditional on teacher-accepted examples; exclusions can make
the cohort easier or change its composition, and must be discussed.

---

# 18. Human audit of synthetic supervision

After prompt and shared-cohort freeze, sample up to five accepted training reports
per verdict cell, seed 42, without replacement: at most ten reentrancy reports. Prefer distinct groups; publish available/selected counts and shortages.

The human assesses consistency with the known scoped verdict, location plausibility,
explanation grounding, exploit plausibility, and mitigation appropriateness.
Use pass/fail, with N/A only for genuinely inapplicable ABSENT fields. This audit
describes teacher noise separately from the upstream-label audit and reviewed test.
Do not delete individually weak but automatically valid reports after seeing the
audit. Systematic protocol failures must be reported before a new version/run;
they are not repaired by hidden cherry-picking.

---

# 19. Student model

## Locked model

**`Qwen/Qwen2.5-Coder-1.5B-Instruct`**

Reasons:

- small enough to fit the “small student model” research framing;
- code-specific pretrained/instruction-tuned model;
- practical for QLoRA on common Colab GPUs;
- public Hugging Face model with permissive Apache-2.0 licensing;
- sufficiently capable to make zero-shot vs. fine-tuned comparison meaningful.

Do not replace the student with a larger model unless the 1.5B model is technically unusable.

---

# 20. Model conditions and fair comparison

Exactly three weight conditions:

| Weights | Training target | Evaluation modes |
| --- | --- | --- |
| Base | None | Base-Label and Base-Report |
| Label-SFT | PRESENT or ABSENT | Verdict output |
| Report-SFT | Complete semantic report with verdict | Structured output |

All consume the same check/scope/source/assumption payload. The two adapters use
the same base revision, train/validation accepted IDs, ordering seed, epochs,
QLoRA settings, and validation-selection rule. Assistant-only loss applies; do
not train on source/prompt tokens. Completion lengths and compute differ and are
reported. No class-discovery credit is awarded for the supplied check name.

Compare Report-SFT versus Base-Report for the format-matched RQ1, Label-SFT versus
Base-Label for verdict-only adaptation, and Report-SFT versus Label-SFT for RQ2.
Evaluate all four modes on identical frozen test queries. Validation loss selects
checkpoints within a condition only; losses across formats are not comparable.
No extra trained architecture or retraining on held-out data is introduced.

---

# 21. Student prompts

Version `student_label_v2.1.txt`, `student_report_v2.1.txt`, and canonical check
definitions. The label instruction requests exactly PRESENT or ABSENT for the
given check and resolved scope. The report instruction requests raw semantic JSON
in schema order: the evidence-ordered `analysis` first, then the verdict and the
verdict-dependent fields. Both explicitly limit conclusions
to the supplied source and supported assumptions.

The identical user payload supplies the canonical check/definition, scope, any
supported compiler/EVM assumptions, and numbered full source. The model must
infer the verdict. Do not include upstream labels, quality tier, collection name,
IDs encoding a verdict, gold lines, review outcomes, or audit prose. Function
scope is an explicit assessment target, not evidence of whether it is vulnerable.
Freeze prompt bytes/hashes; no per-dataset prompt variations or held-out examples.

---

# 22. QLoRA training configuration

Use Hugging Face Transformers + TRL + PEFT + bitsandbytes.

Do not use a notebook as the canonical implementation. Training must be runnable from normal Python modules/scripts so the same code works locally or through Colab CLI.

## Locked default hyperparameters

```yaml
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
max_seq_length: 8192
quantization: 4bit
bnb_4bit_quant_type: nf4
bnb_4bit_use_double_quant: true
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
lora_bias: none
lora_targets:
  - q_proj
  - k_proj
  - v_proj
  - o_proj
  - gate_proj
  - up_proj
  - down_proj
learning_rate: 0.0002
num_train_epochs: 3
per_device_train_batch_size: 1
per_device_eval_batch_size: 1
gradient_accumulation_steps: 4
weight_decay: 0.01
warmup_ratio: 0.05
lr_scheduler_type: cosine
max_grad_norm: 1.0
gradient_checkpointing: true
packing: false
seed: 42
```

Use the same pinned revision as the tokenizer:
`2e1fd397ee46e1388853d2af2c993145b0f1098a`.
On one GPU the effective batch is 4 queries. Keep this locked setting unchanged;
the actual accepted cohort determines the update count and resource estimate.
Before training, report accepted queries, effective batch, planned update count
(`3 * ceil(N_train / 4)` with the final partial accumulation flushed each epoch),
and actual trainer scheduler/warmup steps. Verify trainer behavior against this
plan; save actual updates. Do not claim an update count from source availability
is the final training count. Check the 8192-token memory requirement in an
explicitly authorized runtime before a full job; report capacity failures rather
than silently shortening inputs or changing hyperparameters.

Precision:

- use BF16 when the selected GPU supports it;
- otherwise use FP16.

Optimizer:

- `paged_adamw_8bit` where supported.

Loss:

- calculate training loss on assistant/completion tokens only;
- do not train the model to reproduce the user prompt or source-code input.

Checkpoint selection (v2.2):

- at the end of each epoch, greedily decode the frozen validation cohort with the
  condition's own inference settings (Section 24);
- retain the checkpoint with the highest validation binary macro-F1 (INVALID counts
  as wrong); ties go to lower validation loss, then the earlier epoch;
- log validation loss as well, but never compare losses across conditions;
- save the selected adapter plus tokenizer/config metadata.

Do not run hyperparameter sweeps. If training is numerically unstable, make the minimum necessary change and document it.

---

# 23. Google Colab CLI workflow

Training is performed on Google Colab through the official `google-colab-cli` tool.

Install locally with:

```bash
uv tool install google-colab-cli
```

Preferred accelerator:

1. **L4**
2. T4 fallback
3. A100 if available/desired

The project must be written so no code changes are required between GPU types.

Recommended persistent workflow:

```bash
colab new -s audit-train --gpu L4
colab status -s audit-train
colab ssh -s audit-train
```

Inside the remote runtime, clone/sync the repository, install the locked Python environment, and run the normal project CLI commands.

Artifacts are then downloaded with `colab download` before stopping the runtime.

A convenience script may automate setup, but the underlying training commands must remain plain Python/`uv` commands and must not depend on hidden notebook state.

Required training outputs:

- Label-SFT adapter archive;
- Report-SFT adapter archive;
- training/eval loss logs;
- resolved configuration YAML/JSON;
- environment/package-version snapshot.

Do not rely on the Colab VM as permanent storage.

---

# 24. Deterministic inference and invalid outputs

Use greedy generation (`do_sample=false`) with maximum 16 new tokens for verdicts
and 512 for reports. Record model, prompt, tokenizer, generation config, raw
outputs, and query/input hashes. Inference requires the frozen evaluation list;
it cannot discover extra known labels from a data directory.

For label outputs, trim surrounding whitespace only; exactly PRESENT or ABSENT
is valid. Everything else is INVALID. For reports, parse raw JSON with duplicate
key rejection and validate the complete semantic/contextual schema. Markdown
fences, partial JSON, wrong types, out-of-bounds locations, extra fields, or
inconsistent ABSENT fields are failures. Never repair with another model, regex
extraction, or label fallback. A schema-invalid report predicts INVALID.

INVALID is incorrect for every reference verdict, remains in all denominators,
and is never treated as a correct negative. It is not a third gold label. Keep
valid-JSON and full-schema-valid rates separate. No test teacher calls are allowed.

---

# 25. Evaluation cohorts

1. **Reviewed primary test:** the Section 10 held-out human-reviewed queries;
   primary RQ1/RQ2 evidence. All four evaluation modes use exactly this list.
2. **Secondary merged test:** remaining eligible queries in the same reserved
   held-out groups, labeled by their evidence tier. Report separately; do not
   pool with the primary set or present its size as locally reviewed evidence.
   v2.2 also reports the **whole matched held-out fold** (primary ∪ secondary,
   final labels) with the same metrics and group intervals, as a headline next to
   the primary result, because the 40-query primary set alone detects only large effects.
3. **SmartBugs external:** compatible positive queries with independent lines,
   after protected-group exclusion and taxonomy/scope validation. No train,
   validation, prompt tuning, or teacher targets. Never infer reentrancy absence
   from a non-reentrancy label. Describe its curated/educational mix separately from
   real-source development.
4. **Modern audit challenge:** inactive in v2.2; report it as unavailable. When
   active: only verified, frozen FORGE findings, reserved by
   project/group before development splitting. Use compatible full-source queries
   and independent audit locations. Report positive-case transfer/localization
   and actual support; do not invent negatives from patches or audit silence.

The external sets do not repair primary support failures and are not used for
checkpoint selection. If a source/check has only positives, report positive
recall, invalid/validity rates, and localization where available, not specificity
or binary macro-F1. An empty challenge produces an explicit unavailable entry,
not fabricated zero performance or a new dataset substitution.

---

# 26. Metrics and uncertainty

## 26.1 Primary binary macro-F1

Each primary check c is a binary task with gold PRESENT/ABSENT and predicted
PRESENT/ABSENT/INVALID. Compute ordinary per-label precision, recall, and F1 for
the **two gold labels**, explicitly including INVALID in the false-negative count
of its true label. It is never a true negative and is never a third gold class.
For label l: TP is gold=l and pred=l; FP is gold!=l and pred=l; FN is gold=l and
pred!=l, including INVALID. Use `zero_division=0` with the explicit label list.

Define `B_c = (F1_PRESENT,c + F1_ABSENT,c) / 2`. This penalizes invalid outputs
on negatives as well as positives; positive-class F1 alone would not do so.

```text
primary_score = (F1_PRESENT + F1_ABSENT) / 2
```

Both polarities must satisfy the reentrancy support gates. Otherwise the primary
score is unavailable. This measures scoped binary reentrancy judgments; it does
not measure discovery across vulnerability categories. The balanced primary
review sample does not estimate deployment prevalence or real-world positive
predictive value.

Also report each check's PRESENT precision/recall/F1, ABSENT F1, accuracy, raw
counts, invalid rate, and 2-by-3 confusion matrix. Report pooled query accuracy
only as secondary. Slice by original collection, scope, compiler/EVM context,
evidence tier, and reviewed reentrancy mechanism where available, with explicit
denominators. Unsupported/single-polarity slices have null binary macro-F1 rather than misleading numbers. Include the
constant ABSENT and training-only per-check majority verdict baselines (ties ->
ABSENT). Also report an original-collection/check majority baseline learned from
training metadata, falling back to the per-check majority for unseen collections;
this is a diagnostic for collection shortcuts, not a deployable code classifier.
These baselines require no additional model training or test-label fitting.

v2.2 adds, all fitted on the training partition only and scored on every test view:
a (scope kind, first pragma) majority baseline, and a TF-IDF (identifier/operator
unigrams+bigrams over the scoped code) logistic-regression baseline with fixed,
untuned settings. Also report macro-F1 over schema-valid outputs only, next to the
strict score, and slices by collection, scope kind and pragma, including the
within-SCRUBD-CD slice.

## 26.2 Paired uncertainty

Use a paired cluster bootstrap over **group IDs**, retaining every selected query
from a sampled group and its multiplicity, with identical draws for all model
modes. Seed 4242; target 2,000 valid replicates, at most 20,000 attempted draws.
Draw the original number of unique test groups with replacement. A draw missing
either polarity of a required check cannot define the primary score: discard it,
count it, and try the next draw. If fewer than 2,000 valid replicates are available,
report insufficient bootstrap support rather than silently changing the method.

Report percentile 95% intervals for primary scores and paired differences:
Report-SFT minus Base-Report, Label-SFT minus Base-Label, and Report-SFT minus
Label-SFT. Record support, valid/invalid draws, and per-query predictions. These
intervals reflect held-out group sampling, not multiple training seeds, annotator
uncertainty, or proof of statistical power. Do not treat overlapping point
estimates or a small observed difference as a definitive conclusion.

## 26.3 Structured validity

For Base-Report and Report-SFT report valid-JSON and complete-schema-valid rates
over **all** queries, plus in-bounds location coverage on gold-positive queries.
Keep failures in the denominator. No repair, retry, or substitution at evaluation.

## 26.4 Localization

Use only gold-PRESENT queries with independently supplied or human-verified
vulnerable lines mapped to the exact input and the same check/scope. Main
localization evidence is SmartBugs; also report reviewed-test/FORGE subsets when
available. Function scope boundaries and teacher locations are not line gold.

A verdict-correct hit requires a schema-valid PRESENT report whose inclusive
line interval contains at least one independent vulnerable line for this query.
Use all eligible gold-positive queries as denominator; ABSENT, INVALID, missing,
or out-of-bounds reports score zero. There is no separate class-correct score
because the check is supplied. If several findings satisfy one check, locating
any independently annotated one can score a hit; this does not measure exhaustive
finding recall.

Also report `(end-start+1)/source_line_count` and the number of distinct annotated
lines inside the interval divided by interval length. Average these only over
valid PRESENT reports with in-bounds locations; state denominator/coverage and
use null if none. Whole-file spans can hit but show poor precision/large spans.
Sparse annotation precision measures agreement with known lines, not proof that
other lines are irrelevant. Store all per-query scores.

## 26.5 Explanatory quality

Use the human rubric in Section 27. Teacher text overlap, BLEU/ROUGE, severity
agreement, and schema validity alone do not establish technical correctness.

---

# 27. Blinded human report evaluation

Compare Base-Report and Report-SFT on up to **25 reviewed-primary-test queries**,
without replacement. Retain the 25-query report-evaluation budget; allocate
round-robin over PRESENT then ABSENT, skipping exhausted cells. Choose from sorted IDs with seed 42, preferring distinct groups; publish
actual allocation and any group reuse. This is separate from label review.

Generate/preserve both outputs for every selected query, including failures.
Randomize A/B assignment per query with seed 42; store the model key separately
until ratings are complete. Show the canonical query/source/assumptions, reviewed
reference verdict, and both raw outputs, not the model names. No selective removal
of invalid, wrong-verdict, or embarrassing examples.

Use 0–2 ratings:

- Explanation grounding: 0 contradicted/generic/missing, 1 partly grounded but
  incomplete, 2 technically grounded in the supplied code and requested scope.
- Exploit plausibility on gold positives: 0 implausible/missing, 1 broadly plausible
  but incomplete, 2 concrete and consistent with supported assumptions.
- Mitigation appropriateness on gold positives: 0 wrong/missing, 1 directionally
  correct but vague, 2 specific and addresses the behavior.
- Severity plausibility on gold positives: 0 implausible/missing, 1 questionable
  but defensible, 2 reasonable under the supplied context.

On gold negatives, only grounding applies; separately record false vulnerability
claims and unsupported global-security claims. Wrong ABSENT predictions on gold
positives do not make missing positive criteria N/A; they score zero. Schema
failure is reported separately; if meaningful prose remains, rate it by the same
rubric, otherwise use zero for applicable criteria. Missing output is never dropped.

Report per-criterion means/denominators and paired grounding preference/ties.
One primary human rater is sufficient; identify their role and limitations, not
an invented expert panel. If a second independent rater participates, preserve
separate scores and report agreement. No LLM judge replaces this evaluation.

---

# 28. Required tables and dataset card

Generate all tables from actual machine-readable artifacts.

- **Dataset flow:** native assessments -> resolvable/eligible judgments -> unique
  queries/groups -> reviewed and frozen cohorts -> accepted SFT cohort. Include
  every exclusion/rejection reason; candidate estimates are not frozen counts.
- **Composition:** family/check/polarity by split, original collection, scope,
  compiler era, review tier, source files, known projects, groups, and independent
  location coverage. Unknown project coverage and compiler-era concentration are
  mandatory, not hidden in a total row.
- **Primary results:** all four evaluation modes, reentrancy binary macro-F1,
  primary score with group interval, paired differences, accuracy,
  invalid rate, and constant baselines. Secondary/external results
  remain separate.
- **Reports:** JSON/schema validity, localization hits and coverage, span fraction,
  annotated-line precision, and blinded grounding/exploit/mitigation/severity.
- **Resources:** accepted query/context/completion tokens, teacher attempts/usage,
  rejection rates, optimizer steps, GPU time, and hardware/config versions.

Publish a dataset card documenting origin/licenses, construction and reviewer
roles, intended scoped task, all three label states, native coverage differences,
reentrancy mechanism/context limits, selection bias, exact/clone-group overlap policy and residual risks,
code/version assumptions, exclusions, splits, known pretraining contamination
limits, and prohibited claims. Do not describe a combined derivative as newly
discovered vulnerabilities or newly independent examples.

---

# 29. Error analysis

After frozen evaluation, export deterministic examples of false positives,
false negatives, INVALID outputs, incorrect localization, unsupported callback/guard
assumptions, and plausible-looking but ungrounded explanations. Include
compiler-era, mechanism, and source/scope patterns. Select by fixed sorted-ID/seed
rules within error strata, not only spectacular failures. Discuss 3–5 examples
in the paper; keep the broader table as a reproducibility artifact. Do not use
error analysis to retune the reported experiment or rewrite its labels.

---

# 30. Reproducibility and artifact contracts

Every release/run records project commit (or null plus file hashes before the
first commit), spec/config/schema versions, upstream revisions and annotation
hashes, original collection ancestry, all normalization/grouping/mapping rules,
human review decisions and dates, seeds, dataset/cohort freeze hashes, teacher/
student/prompt/tokenizer versions, package lockfile and Python environment,
hardware/GPU/CUDA details, input/output hashes, and actual usage/steps.

The v2.1 inventory in `data/processed/reentrancy-v2.1/` (release input, unchanged
candidate semantics):

```text
artifacts.parquet                 # source/alias and provenance inventory
assessments.parquet               # native judgments, coverage and evidence states
queries.parquet                   # mechanically resolved candidate queries
exclusions.jsonl                  # rejected assessments and reasons
conflicts.jsonl                   # unresolved opposing reentrancy evidence
groups.jsonl, group_edges.jsonl   # connected components and link evidence
ingestion_issues.jsonl            # upstream missing-code/link issues
taxonomy.json, effective_config.json, provenance.json
dataset_statistics.json, dataset_statistics.csv
dataset_manifest.json             # hashes and content fingerprint, written last
```

The v2.2 release in `data/processed/reentrancy-v2.2/`:

```text
release_queries.jsonl             # balanced cohort: partition, match pair, upstream label
eligible_pool.jsonl               # all eligible queries before cap/matching
release_exclusions.jsonl          # unknown/unverified/coverage/cap/surplus reasons
split_assignments.jsonl           # group -> partition
split_attempts.json               # every seed attempt and its support summary
review_queue_audit.jsonl          # fixed training-label audit queue
review_queue_primary.jsonl        # fixed held-out primary-test queue
release_statistics.json, effective_release_config.json, provenance.json
release_manifest.json             # hashes and content fingerprint, written last
# written by freeze only, after complete human review:
train.parquet, validation.parquet, test_primary.parquet, test_secondary.parquet
external_smartbugs.jsonl          # protected positives with independent lines
reviews.jsonl                     # the human decisions applied
dataset_freeze.json               # hashes, gates, audit results, provenance
```

Human decisions are recorded locally in `data/reviews/reentrancy-v2.2.jsonl`
(gitignored) by `scripts/review_labels.py`.

Primary and secondary test query lists are disjoint; their groups may coincide
because both are held out. Source-containing artifacts/review prose remain
gitignored. Commit small permissible manifests, schema/configs, dataset card,
final metrics, and code; do not commit credentials, raw source dumps, or weights.
The inventory baseline additionally reports source/evidence-tier/scope/polarity
cells and a first-pragma compiler-era screen. These are descriptive candidate
counts, never evidence of human review, semantic eligibility, or statistical
power. `scripts/validate_dataset.py` verifies the persisted baseline mechanically
and writes an optional small report outside the dataset directory.

The manifest is written last, hashes its artifacts, and has an explicit
inventory/provisional/frozen state. Incomplete review cannot produce a frozen
release. Repeat builds from identical inputs/decisions must reproduce content
hashes regardless of input order; timestamps stay outside deterministic payloads.

Teacher records and `shared_cohort.json` are later artifacts linked to that
freeze. Use `runs/teacher`, `runs/label-sft`, `runs/report-sft`, and `runs/eval`
directories with effective config, logs, manifest hashes, and real result files.
Do not promote an exploratory /tmp download or approximate union count into a
release without the documented fetch/build/review path.

---

# 31. Architecture

Keep normal typed modules under `src/audit_distill/`:

- `data/`: source-specific adapters (DAppSCAN, SmartBugs, SCRUBD, Salzano, CGT,
  ScBench, FORGE), comment/identity/scope normalization, evidence mapping,
  conflicts, groups, split, review/freeze, and build orchestration.
- `teacher/`: isolation, transport/batching, generation, cache, usage, validation.
- `training/`: shared cohort/chat formatting, QLoRA model setup, two SFT commands.
- `inference/`, `evaluation/`, `reporting/`: deterministic output/parsing,
  scoped metrics/bootstrap/localization/human scoring, dataset card and paper assets.

Use Pydantic records, YAML configs, exported JSON schemas, and thin scripts under
`scripts/`. Reuse existing correct comment/lexical/token-budget utilities after
regression checks. Replace file-level assumptions where necessary; do not hide a
parallel unmaintained pipeline behind an adapter framework. No database, service,
notebook-only logic, crawler framework, or new model architecture is needed.

---

# 32. Python project rules

- Python >= 3.12 unless an ML dependency requires 3.11; if so, lock 3.11 and document why.
- Use `uv` for dependency/environment management.
- Use `pyproject.toml`; no manually maintained `requirements.txt` as source of truth.
- Core logic lives under `src/audit_distill`, not in giant scripts.
- Scripts are thin CLI entry points.
- Use type hints.
- Use Pydantic for structured record/report models.
- Use `pathlib` for paths.
- Use standard `logging`, not scattered `print` calls for long pipelines.
- Long-running commands must show progress.
- Generation/training/evaluation must be resumable where practical.
- Avoid unnecessary abstractions and framework layers.
- No database is required; JSONL/Parquet/CSV files are sufficient.
- Prefer Parquet for processed tabular datasets and JSONL for generation records.

---

# 33. Dependencies

Expected core dependencies:

```text
pydantic
pydantic-settings
pyyaml
pandas
pyarrow
scikit-learn
numpy
transformers
trl
peft
accelerate
bitsandbytes
datasets
torch
matplotlib
rich
tqdm
pytest
```

Pin versions through `uv.lock` once the pipeline works.

Do not add large frameworks unless required.

---

# 34. Configuration

`configs/project.yaml` declares spec/data/schema version 2.1, immutable approved
source pins, local paths, output namespace, tokenizer/budgets, comment and
identity policy, scope/parser versions, grouping thresholds, split seed range,
review quotas/support gates, teacher model/CLI/isolation/transport/cache policy,
sampling seeds, and output paths. `configs/taxonomy.yaml` contains the Section 7
definitions and verified source/property/polarity mappings, with evidence notes.
`configs/training.yaml` keeps the unchanged QLoRA values in Section 22.

Save fully resolved configs and hashes. Reject unknown fields and incompatible
versions rather than falling back to old classes or negative rules. Dataset
builds, tests, and dry runs must never implicitly launch teacher or GPU work.
Only current schemas under `schemas/v2.1/` and active configs are maintained.
Candidate/check records are restricted to REENTRANCY; incompatible versions must
fail explicitly. Merely changing a version field is not a migration.

---

# 35. CLI workflow to implement

Inventory build, inspection, mechanical validation, the v2.2 split/queue stage,
the human review tool and freeze are implemented. The
remaining commands below describe v2.1 acceptance behavior for later phases.
Keep README commands synchronized with actual code. The thin script names may
reuse existing names, with explicit stages for incomplete review:

```bash
uv sync --locked
uv run pytest
uv run python scripts/fetch_data.py
uv run python scripts/build_dataset.py --stage inventory
uv run python scripts/validate_dataset.py
# Remaining stages below are acceptance behavior, not yet implemented:
uv run python scripts/build_dataset.py --stage split        # implemented (v2.2)
# Human completes the fixed review queues; no teacher/model is run here.
uv run python scripts/review_labels.py audit                # implemented
uv run python scripts/review_labels.py primary              # implemented
uv run python scripts/build_dataset.py --stage freeze       # implemented
uv run python scripts/generate_teacher.py --split train --pilot --dry-run
# Only after explicit authorization for each real pilot/production run:
uv run python scripts/generate_teacher.py --split train --pilot
# Freeze prompt, then inspect production usage before authorization.
uv run python scripts/generate_teacher.py --split train --dry-run
uv run python scripts/generate_teacher.py --split validation --dry-run
uv run python scripts/generate_teacher.py --split train
uv run python scripts/generate_teacher.py --split validation
uv run python scripts/build_student_dataset.py
uv run python scripts/audit_teacher_sample.py
# Only in an explicitly authorized Colab runtime, after cohort verification:
uv run python scripts/train_label.py --config configs/training.yaml
uv run python scripts/train_report.py --config configs/training.yaml
uv run python scripts/evaluate.py
uv run python scripts/build_human_eval.py
# Human fills blinded ratings, then:
uv run python scripts/score_human_eval.py
uv run python scripts/make_paper_assets.py
```

Freeze must fail with actionable missing-review/support reasons instead of
producing an apparently final corpus. Smoke mode uses tiny fixtures, mock teacher
responses, and no GPU/subscription calls. Each real generation/training command
must verify the dataset and shared-cohort prerequisites that apply to it.

---

# 36. Authentication and secrets

Teacher generation must use Codex CLI authenticated with the user's ChatGPT account. No `OPENAI_API_KEY` is required for the planned experiment.

Do not add an API-key dependency to the default pipeline. Do not commit Codex authentication/session data, access tokens, cookies, or other credentials.

The generator should fail clearly if `codex` is unavailable or not authenticated.

If Hugging Face authentication is later required for model downloads, keep any `HF_TOKEN` local and gitignored.

---

# 37. Required tests and invariants

Preserve existing valid comment, lexical identity, line numbering, fetch, schema,
and budget tests. Assertions encoding retired experiments must not survive as
claims about the current protocol.
Use meaningful adversarial fixtures for these behaviors:

- Each source adapter maps exact pinned formats, provenance and origin correctly;
  missing code/metadata links, truncated trees, and version mismatches fail clearly.
- Multi-label files retain compatible known queries; duplicate support creates
  one query; distinct reentrancy scopes share a source and split without collapsing.
  Inactive native properties stay in the ledger without supervised queries.
- Blank labels, unannotated DAppSCAN files, tools, and non-target findings cannot
  create ABSENT; explicit scope/property coverage is necessary for any derivation.
- Negative function/subtype labels never become broad file/family negatives;
  ambiguous declarations, unresolved guards, unsupported assumptions, and audit
  version mismatches are quarantined/excluded rather than guessed.
- Conflicts require semantic/scope compatibility; broad-negative/narrow-positive
  contradictions are detected, distinct scopes are retained, and decisions apply
  to aliases consistently without majority voting.
- Comments blank without moving coordinates or changing literals; token identity
  preserves spellings/boundaries; line numbering has no phantom final line.
- Payload hashes change with source coordinates, check, scope, or assumptions;
  no student payload contains reference verdict/evidence/label-bearing metadata.
- Project/version/clone edges merge transitively, protected sources reserve entire
  eligible components, common unused libraries do not falsely imply one project,
  and no admitted hash/group/known-project overlap exists across partitions.
- Split/review ordering is deterministic; quotas count groups correctly, polarity
  corrections/replacements stay held out, and partial reviews/support shortages
  cannot silently freeze a dataset or remove a required primary check.
- V2.1 reports enforce verdict/types/field constraints and contextual bounds;
  unsupported teacher responses reject both SFT records without relabeling.
- Partial per-item failure preserves other valid batch items; invalid ID maps
  fail closed; retries are bounded; resumability binds full generation identity.
- Exact 480/6000/8192 token boundaries, both chat formats, same accepted cohort,
  assistant-only loss masking, and post-rejection support gates are enforced.
- All invalid predictions remain incorrect; binary-label F1 includes invalid
  negatives as false negatives for ABSENT; missing-polarity handling,
  constant baselines, and paired group-bootstrap multiplicity match hand fixtures.
- Independent-line hit/precision/span metrics use declared denominators, never
  teacher locations or function scope as gold; malformed predictions are misses.
- Human selection/blinding retains failures, applies N/A only to gold-negative
  criteria, preserves the key, and never certifies model-generated human reviews.
- Source/config/artifact hashes, version rejection, output namespaces, and
  deterministic repeat builds hold; no ordinary test/build makes teacher calls.

Before teacher use, isolation tests must deny sentinel-file access outside the
allowed view and prove disabled external/tool facilities; reject prohibited tool
events even if the output otherwise validates. Test these with local mocks first.
`uv run pytest` is the repository-wide default check; phase completion requires
that phase's invariants and inspected artifacts, not merely a passing test suite.

---

# 38. Implementation phases and migration order

1. **Foundation migration:** v2.1 record/config/schema types, canonical checks,
   partial labels and scope models, strict version compatibility, tests. Preserve
   reusable source/identity/budget utilities without retaining obsolete pipelines.
2. **Dataset construction:** pinned adapters, evidence/negative rules, scope and
   context validation, conflicts, clone/project groups, protected external roles,
   deterministic split/review queues, real human review import, dataset card,
   statistics and freeze. Exit only when reproducible artifacts, integrity tests,
   all primary support/breadth gates, and required reviews pass. Preparing queues
   is progress, not completion of the human review or frozen dataset.
3. **Teacher:** isolated pinned Codex runner, bounded batches/retries/unsupported
   responses, zero-call estimates, cache/usage and audits. Implement with mocks;
   an authorized availability-aware pilot must demonstrate actual isolation,
   schema compatibility and prompt quality before production.
4. **Student data:** canonical chat formatting, assistant-only loss, identical
   accepted IDs, complete token checks, support revalidation, shared cohort hash.
5. **Training:** shared QLoRA setup and Colab workflow, smoke verification then
   explicitly authorized real jobs, adapters/logs/configs recovered locally.
6. **Evaluation:** all four modes, strict output parsing, primary/secondary/
   external metrics, group intervals, independent localization and raw exports.
7. **Human report evaluation:** fixed paired sample, blinded A/B cards and key,
   actual human ratings, denominator-aware scoring and optional second-rater support.
8. **Paper/reproducibility:** dataset card, final tables/plots, accurate README,
   ACL paper and limitations from real results.

Do not jump over a failed earlier-phase gate. The candidate baseline is not a
completed Phase 2 release; Phases 3–8 have not become authorized real runs merely
because this design was approved.

---

# 39. Paper plan

Use the required ACL format, at most eight content pages excluding references:

- Introduction (~0.75–1 page): plain-language smart contracts/Solidity, scoped
  code-to-text assessment, synthetic supervision, and RQ1–RQ3.
- Related Work (~1 page): Solidity datasets and weaknesses, LMs for code/auditing,
  synthetic supervision and QLoRA. Cite the actual source papers/snapshots, not
  headline counts as validation. Include recent relevant work and primary model/
  LoRA/QLoRA references, with verified bibliographic details.
- Methods (~2–2.5 pages): one precisely defined reentrancy check,
  partial labels, full context/scoped queries, evidence and human review, groups,
  teacher isolation/schema, matched conditions, and precise metrics.
- Results (~1.5–2 pages): actual dataset/support flow, verdict and report metrics,
  paired uncertainty, human results, and a few deterministic errors.
- Discussion (~1 page): answer the RQs; discuss upstream/teacher noise, review
  limitations, historical compiler/EVM behavior, reentrancy-only scope and source/scope
  confounding, unknown project ancestry/near clones, pretraining exposure,
  acceptance selection, unequal target-token exposure, one model/seed/rater,
  limited support, and lack of deployment-prevalence/production-safety evidence.
- Conclusion/future work (~0.5 page): empirical findings and bounded extensions.

Keep full dataset card, source/subtype matrices, audit ledgers, confidence details,
and reproducibility commands in repository artifacts referenced by the paper.
No placeholder metric may look like an observed result.

---

# 40. Figures

Use one small pipeline figure: pinned real source/assessments -> scoped partial-label
ledger -> conflict/clone grouping and reviewed freeze -> matched Label-SFT and
Report-SFT -> identical held-out verdict/report evaluation. Show external and
review evidence kept outside teacher generation. Add check-specific 2-by-3
confusion matrices or uncertainty plots only when they add information within
the page limit. Generate scientific figures from real metrics, not screenshots.

---

# 41. Permitted claims

If supported by actual results, the paper may claim that synthetic report
supervision changes scoped binary assessment/report behavior for this reentrancy check,
that QLoRA adapts this small model on this corpus, and that some measured transfer
occurs to the protected benchmarks. Describe the merged dataset as a traceable
derivative with partial labels and declared human review.

Do not claim exhaustive vulnerability discovery, that ABSENT means secure,
independent projects merely from different addresses/hashes, teacher text as gold,
statistically powered small improvements merely from passing support gates,
expert labels merely from a dataset name, general vulnerability competence from
reentrancy alone, modern exploitability from historical labels, or readiness
for production auditing. Do not motivate reentrancy as the most common current
attack without supporting population evidence. Passing support gates does not
establish statistical power.

---

# 42. Definition of done

- [ ] V2.1 config, records, schemas, parser contracts and required invariants pass.
- [ ] Pinned sources/assessments rebuild reproducibly with retained provenance/licenses.
- [ ] Partial labels, scope, context, conflicts, and unknown exclusions are inspectable.
- [ ] Clone/project groups and protected-source separation pass; residual risks are stated.
- [ ] Training-label audit and primary-test human review are actually complete.
- [ ] All reentrancy polarity/group/source gates pass; freeze is hashed.
- [ ] Real teacher pilot is authorized, isolated, reviewed, and prompt/schema frozen.
- [ ] Train/validation reports and usage/rejection records are complete and resumable.
- [ ] Shared accepted cohort is identical across conditions and passes all budgets/gates.
- [ ] Synthetic-supervision human audit is complete with actual denominators.
- [ ] Both authorized Colab jobs finish and adapters/logs/configs are recovered.
- [ ] All four evaluation modes run on identical frozen lists; primary intervals,
  invalid-output accounting, secondary/external and localization metrics are real.
- [ ] Blinded human report comparison is rated and scored without dropping failures.
- [ ] Dataset card, generated paper tables/figures, accurate README, and code support
  reproduction without private state or committed source/credential dumps.
- [ ] The ACL paper fits eight content pages, references the repository, makes only
  supported scoped claims, and is ready before 2026-09-30 23:59.

A valid exploratory result can show no improvement. An unreviewed dataset, missing
required polarity, fabricated label, or placeholder result is not a completed study.

---

# 43. Implementation behavior

Read this specification completely before research/architecture decisions.
Implement in phase order with small typed modules, deterministic artifacts,
meaningful invariant tests, and truthful progress reports. Ask before changing
the locked protocol, model/resource plan, or scope; ordinary mechanics may adapt
to actual upstream formats when evidence semantics remain unchanged.

Do not edit the spec to legitimize incompatible implementation behavior. Keep README
status and AGENTS instructions synchronized with the approved design while
clearly distinguishing implemented behavior. Never claim queued review is done,
candidate counts are final, or declared isolation settings prove enforcement.
Teacher/GPU actions require explicit user-approved runs after the relevant gates.

---

# 44. Next implementation milestone

The v2.2 provisional split and fixed review queues exist. The next milestone is
the human review and freeze, before meaningful external-resource use:

```text
v2.1 inventory (unchanged)
  -> v2.2 eligibility, group cap, grouped split, per-partition 1:1 matching   [done]
  -> fixed training-audit and primary-test queues                             [done]
  -> human training-label audit (44 cards) and primary review (~40-53 cards)
  -> freeze: apply decisions, recheck gates, hashed dataset_freeze.json
  -> then Phase 3 teacher runner with mocks, and an authorized pilot
```

Report unresolved human decisions and feasibility failures concretely. Do not
launch a teacher pilot to fill label gaps or discover whether the dataset is valid.

---

# 45. Experiment at a glance

```text
Real source + traceable assessments
                |
   scoped PRESENT / ABSENT / UNKNOWN ledger
                |
 evidence checks + alias/clone/project groups
                |
       frozen grouped partitions -------- protected external groups
                |                                   |
        train + validation                    SmartBugs (FORGE inactive)
           /          \                            |
 known verdicts    isolated teacher                  |
           \          /                            |
       same accepted SFT cohort                      |
           /          \                            |
      Label-SFT     Report-SFT                        |
           \          /                            |
       Base comparisons on reviewed held-out queries + external checks
                |
       scoped verdicts, grounded reports, group uncertainty
```

Exactly one vulnerability family, two verdicts, one student, two adapters, and a bounded NLP experiment.
