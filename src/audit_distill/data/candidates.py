"""Produce inspectable scoped candidates; semantic review is an explicit prerequisite."""

from collections import defaultdict
from collections.abc import Callable

from tqdm import tqdm

from audit_distill.data.ledger import Ledger
from audit_distill.data.line_numbers import render_line_numbers
from audit_distill.data.records import Artifact, Assessment, CandidateQuery, Disagreement, Scope
from audit_distill.data.scopes import digest, resolve_scope

ASSUMPTIONS = [
    "Any address that receives a call or ether may be a contract that runs arbitrary code."
]


def canonical_payload(code: str, check: str, definition: str, scope: Scope) -> dict[str, object]:
    """The exact model input shared by teacher, student and all evaluation modes."""
    return {
        "check_id": check,
        "definition": definition,
        "scope": {"kind": scope.kind, "name": scope.name},
        "assumptions": ASSUMPTIONS,
        "source": render_line_numbers(code),
    }


def candidates(
    ledger: Ledger, count_tokens: Callable[[str], int]
) -> tuple[list[CandidateQuery], list[Disagreement], list[dict[str, str]]]:
    resolved: dict[str, Scope] = {}
    scope_cache: dict[tuple[str, str, str], Scope | str] = {}
    exclusions: list[dict[str, str]] = []
    by_identity: dict[str, list[Assessment]] = defaultdict(list)
    pending: dict[str, list[tuple[Assessment, Artifact, Scope, str]]] = defaultdict(list)
    by_id = ledger.artifacts
    for assessment in tqdm(ledger.assessments, desc="Validating scoped evidence", mininterval=5):
        artifact = by_id[assessment.artifact_id]
        if not assessment.candidate_checks:
            continue
        if assessment.native_verdict == "UNKNOWN":
            exclusions.append(
                {"assessment_id": assessment.assessment_id, "reason": "unknown_native_label"}
            )
            continue
        if "excluded_original_collection" in assessment.issues:
            exclusions.append(
                {
                    "assessment_id": assessment.assessment_id,
                    "reason": "excluded_original_collection",
                }
            )
            continue
        identity = artifact.code_identity_sha256
        if identity is None:
            exclusions.append(
                {"assessment_id": assessment.assessment_id, "reason": "unreadable_source"}
            )
            continue
        by_identity[identity].append(assessment)
        key = (artifact.artifact_id, assessment.native_scope_kind, assessment.native_scope)
        if key not in scope_cache:
            try:
                scope_cache[key] = resolve_scope(
                    artifact.code, assessment.native_scope_kind, assessment.native_scope
                )
            except ValueError as error:
                scope_cache[key] = str(error)
        scope = scope_cache[key]
        if isinstance(scope, str):
            exclusions.append(
                {
                    "assessment_id": assessment.assessment_id,
                    "reason": "unresolved_scope",
                    "detail": scope,
                }
            )
            continue
        resolved[assessment.assessment_id] = scope
        if artifact.code_tokens is None:
            artifact.code_tokens = count_tokens(render_line_numbers(artifact.code))
        if artifact.code_tokens > ledger.config.tokenizer.max_code_tokens:
            exclusions.append(
                {"assessment_id": assessment.assessment_id, "reason": "overlength_source"}
            )
            continue
        for check in assessment.candidate_checks:
            query_id = digest([identity, scope.token_identity, check, ASSUMPTIONS])
            pending[query_id].append((assessment, artifact, scope, check))

    disagreements: list[Disagreement] = []
    affected: set[str] = set()
    for identity, assessments in sorted(by_identity.items()):
        buckets: dict[str, list[Assessment]] = defaultdict(list)
        for assessment in assessments:
            for check in assessment.candidate_checks:
                buckets[check].append(assessment)
        for check, rows in sorted(buckets.items()):
            positives = [a for a in rows if a.native_verdict == "PRESENT"]
            negatives = [a for a in rows if a.native_verdict == "ABSENT"]
            links: set[str] = set()
            exact_conflict = False
            for p in positives:
                for n in negatives:
                    ps, ns = resolved.get(p.assessment_id), resolved.get(n.assessment_id)
                    # Unresolved scope cannot establish a contradiction; keep it excluded.
                    if ps is None or ns is None:
                        continue
                    if not (ns.start_token <= ps.start_token and ps.end_token <= ns.end_token):
                        continue
                    links.update([p.assessment_id, n.assessment_id])
                    pa, na = by_id[p.artifact_id], by_id[n.artifact_id]
                    pc = p.metadata.get("original_collection", pa.original_collection)
                    nc = n.metadata.get("original_collection", na.original_collection)
                    exact_conflict |= pc == nc and p.native_property == n.native_property
            if links:
                affected.add(identity)
                disagreements.append(
                    Disagreement(
                        disagreement_id=digest([identity, check, sorted(links)]),
                        code_identity_sha256=identity,
                        check_id=check,
                        assessment_ids=sorted(links),
                        kind="same_property_conflict"
                        if exact_conflict
                        else "cross_property_disagreement",
                    )
                )
    result = []
    definitions = ledger.taxonomy["checks"]
    for query_id, copies in sorted(pending.items()):
        copies.sort(
            key=lambda x: (
                not bool(x[0].native_lines and "annotation_line_out_of_bounds" not in x[0].issues),
                x[1].source,
                x[1].revision,
                x[1].path,
                x[0].native_id,
            )
        )
        first, artifact, scope, check = copies[0]
        native = sorted({x[0].native_verdict for x in copies})
        issues = sorted({i for a, _, _, _ in copies for i in a.issues})
        review = {
            "native_check_equivalence",
            "exact_model_input_sufficiency",
            "execution_assumptions",
        }
        if any(
            len(a.candidate_checks) > 1 and a.native_verdict == "PRESENT" for a, _, _, _ in copies
        ):
            review.add("ambiguous_check_mapping")
        if any(a.evidence_tier == "UNVERIFIED" for a, _, _, _ in copies):
            review.add("unverified_native_evidence")
        if artifact.code_identity_sha256 in affected:
            review.add("unresolved_identity_disagreement")
        if "negative_coverage_review_required" in issues:
            review.add("negative_coverage")
        if "annotation_line_out_of_bounds" in issues:
            review.add("native_location_source_alignment")
        roles = {a.role for _, a, _, _ in copies}
        role = (
            "smartbugs_external"
            if "smartbugs_external" in roles
            else "forge_external"
            if "forge_external" in roles
            else "development"
        )
        payload = canonical_payload(artifact.code, check, definitions[check]["definition"], scope)
        proposed = native[0] if len(native) == 1 else "UNKNOWN"
        if "ambiguous_check_mapping" in review or "unresolved_identity_disagreement" in review:
            proposed = "UNKNOWN"
        result.append(
            CandidateQuery(
                query_id=query_id,
                artifact_id=artifact.artifact_id,
                assessment_ids=sorted({a.assessment_id for a, _, _, _ in copies}),
                code_identity_sha256=artifact.code_identity_sha256,
                check_id=check,
                scope=scope,
                native_verdicts=native,
                proposed_verdict=proposed,
                role=role,
                original_collections=sorted(
                    {
                        a.metadata.get("original_collection", art.original_collection)
                        for a, art, _, _ in copies
                    }
                ),
                mechanical_status="PASS",
                issues=issues,
                review_required=sorted(review),
                model_input_sha256=digest(payload),
            )
        )
    return result, disagreements, exclusions
