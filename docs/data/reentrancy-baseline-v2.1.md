# Reentrancy candidate inventory — v2.1

Built from the seven approved pinned sources; mechanical validation passes. The
inventory is the input to the balanced [v2.2 release](reentrancy-release-v2.2.md);
it is not itself a training or evaluation set.

Content fingerprint:
`2ba41c2d507e791b3a0d035e37cd0b579d9632864325be3efdd3be64f4049de9`.

## What the baseline contains

The complete provenance inventory remains: **31,185 source artifacts/aliases**,
**21,493 readable lexical source identities**, and **28,730 native assessments**.
Non-target findings survive in that ledger. There are 24,649 assessments without
an active reentrancy mapping; these are not reentrancy negatives.

Only reentrancy produces active candidates: **2,579 scoped queries**, covering
**2,297 distinct lexical source versions**. Of these, **2,401 development queries**
cover **2,147 source versions** in **1,608 provisional code groups**.

| Development proposed verdict | Queries | Source versions | Supporting groups |
| --- | ---: | ---: | ---: |
| PRESENT | 289 | 240 | 198 |
| ABSENT | 1,926 | 1,775 | 1,381 |
| UNKNOWN | 186 | 156 | 89 |

Queries can share source and group identities. Different scopes on the same
source can have different compatible judgments. Source/group columns must not
be summed to estimate independent contracts or projects.

## Evidence quality

| Development support | Proposed PRESENT | Proposed ABSENT | UNKNOWN |
| --- | ---: | ---: | ---: |
| At least one upstream-reviewed assessment | 225 | 836 | 32 |
| Unverified support only | 64 | 1,090 | 154 |

These are query counts. Upstream-reviewed means documented upstream human
assessment, not local semantic certification. Only the upstream-reviewed rows are
eligible for the v2.2 release; the sampled human audit checks them further.

The source support breakdown is:

| Supporting source | Proposed PRESENT | Proposed ABSENT | UNKNOWN |
| --- | ---: | ---: | ---: |
| DAppSCAN | 89 | 0 | 0 |
| SCRUBD-CD | 92 | 243 | 8 |
| Salzano | 35 | 553 | 21 |
| Selected CGT originals | 64 | 1,090 | 154 |
| ScBench | 9 | 40 | 3 |

Supporting-source counts can overlap, especially across evidence tiers and
repackaged original collections. Source names do not establish independent
collection ancestry. CGT is unverified (its original human-assessment protocol
was not established) and is inactive in v2.2.

## External reservations and modern coverage

- **151 candidates** fall in SmartBugs-protected groups: 123 proposed positives
  and 28 proposed negatives. These are reservations including development aliases,
  not 151 admitted SmartBugs benchmark examples. Only 30 candidate queries have
  native SmartBugs support; benchmark membership requires its own validation.
  Development aliases and their negatives cannot expand the external benchmark.
- **27 FORGE candidates**, in 20 groups, stay reserved and UNVERIFIED; the modern
  challenge is inactive in v2.2.
- Only **16 of the 240 distinct proposed-positive development source versions**
  declare Solidity 0.8. The development source pool remains heavily historical.
  A pragma is a compiler-era screen, not a collection/deployment date or EVM fork.

There are 1,860 total provisional groups, including protected groups without an
active reentrancy candidate. Retaining these contamination references is
intentional. They are not extra supervised examples.

## Limits

- Imbalance: always predicting ABSENT is about 87% accurate on the resolved pool;
  v2.2 therefore balances by matched sampling.
- 158 identity disagreements affect 186 development queries; they stay UNKNOWN
  (no majority voting, no teacher relabeling).
- At the assessment level, 703 active-target judgments exceed the source budget
  (excluded, never truncated), 87 belong to disallowed original collections and
  16 have unresolved scopes. The ledger keeps 7 unreadable artifacts, 999 CGT rows
  without published source and 115 FORGE reports without source.
- Older code, incomplete project ancestry and public pretraining exposure remain.
  Group heuristics do not prove semantic equivalence or independent projects.

## Reproduction

```bash
uv run python scripts/fetch_data.py
HF_HUB_OFFLINE=1 uv run python scripts/build_dataset.py --stage inventory
uv run python scripts/validate_dataset.py
```

The offline option requires the cached pinned tokenizer; no model weights are
downloaded. Two independent builds reproduce the same content fingerprint; see
[`data/manifests/`](../../data/manifests/). Raw sources and code-containing
outputs stay local and gitignored.
