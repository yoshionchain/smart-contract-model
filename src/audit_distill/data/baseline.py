"""Descriptive candidate support; these counts never certify labels or split support."""

import re
from collections import defaultdict

from audit_distill.data.records import Artifact, Assessment, CandidateQuery


def baseline_statistics(
    artifacts: dict[str, Artifact],
    assessments: list[Assessment],
    queries: list[CandidateQuery],
) -> dict[str, object]:
    evidence = {a.assessment_id: a for a in assessments}
    cells: dict[tuple[str, str, str, str], list[CandidateQuery]] = defaultdict(list)
    eras: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for query in sorted(queries, key=lambda q: q.query_id):
        support = [evidence[aid] for aid in query.assessment_ids]
        tier = (
            "has_upstream_reviewed_support"
            if any(a.evidence_tier == "UPSTREAM_REVIEWED" for a in support)
            else "unverified_only"
        )
        cells[query.role, query.proposed_verdict, "evidence", tier].append(query)
        cells[query.role, query.proposed_verdict, "scope", query.scope.kind].append(query)
        for source in sorted({artifacts[a.artifact_id].source for a in support}):
            cells[query.role, query.proposed_verdict, "supporting_source", source].append(query)
        # The canonical model context determines this screen, never an arbitrary alias.
        code = artifacts[query.artifact_id].code
        match = re.search(r"\bpragma\s+solidity\b[^;]*?(0\.\d+)", code)
        era = match[1] if match else "unspecified"
        eras[query.role, query.proposed_verdict, era].add(query.code_identity_sha256)
    return {
        "active_checks": ["REENTRANCY"],
        "candidate_source_identities": len({q.code_identity_sha256 for q in queries}),
        "development_source_identities": len(
            {q.code_identity_sha256 for q in queries if q.role == "development"}
        ),
        "support_cells": [
            {
                "role": role,
                "proposed_verdict": verdict,
                "dimension": dimension,
                "value": value,
                "queries": len(rows),
                "source_identities": len({q.code_identity_sha256 for q in rows}),
                "groups": len({q.group_id for q in rows}),
            }
            for (role, verdict, dimension, value), rows in sorted(cells.items())
        ],
        "compiler_era_cells": [
            {
                "role": role,
                "proposed_verdict": verdict,
                "first_pragma_minor": era,
                "source_identities": len(identities),
            }
            for (role, verdict, era), identities in sorted(eras.items())
        ],
        "notes": [
            "All counts describe candidates, not certified training or evaluation examples.",
            "Supporting sources overlap; repackaged collections are not independent evidence.",
            "A source/group may support multiple scopes, verdicts, or compiler-pragma cells.",
            "Upstream-reviewed support still needs check/scope/context/coverage verification.",
            "The first pragma is a compiler-era screen, not a deployment date or EVM fork.",
            "Protected-group aliases are reservations, not extra benchmark observations.",
        ],
    }
