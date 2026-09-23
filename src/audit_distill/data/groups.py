"""Deterministic evidence-linked components; hashes do not prove independent projects."""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from tqdm import tqdm

from audit_distill.data.identity import solidity_tokens
from audit_distill.data.records import Artifact, CandidateQuery
from audit_distill.data.scopes import declarations, digest
from audit_distill.data.settings import DataConfig

# Solidity 0.8.30 lexical/contextual/reserved words, plus legacy keywords/types/units
# and Yul control words. Builtin identifiers (e.g. msg/require) are alpha-renamed.
# Reference: ethereum/solidity v0.8.30 docs/grammar/SolidityLexer.g4.
KEYWORDS = frozenset(
    """
    abstract address after alias anonymous apply as assembly at auto bool break byte bytes
    calldata case catch constant constructor continue contract copyof days default define
    delete do else emit enum error ether event external fallback false final finney fixed
    for from function global gwei hex hours if immutable implements import in indexed
    inline int interface internal is layout leave let library macro mapping match memory
    minutes modifier mutable new null of override partial payable pragma private promise
    public pure receive reference relocatable return returns revert sealed seconds sizeof
    static storage string struct supports switch szabo throw transient true try type
    typedef typeof ufixed uint unchecked unicode using var view virtual weeks wei while
    years
    """.split()
)


def skeleton(tokens: list[str]) -> list[str]:
    result: list[str] = []
    names: dict[str, str] = {}
    skip = False
    for token in tokens:
        if token == "pragma":
            skip = True
        if skip:
            if token == ";":
                skip = False
            continue
        if token.startswith(('"', "'")):
            result.append("LITERAL_STRING")
        elif token[0].isdigit() or token.startswith(".") and len(token) > 1 and token[1].isdigit():
            result.append("LITERAL_NUMBER")
        elif (
            re.fullmatch(r"[A-Za-z_$][\w$]*", token)
            and token not in KEYWORDS
            and not re.fullmatch(r"(?:u?int|bytes)\d+|u?fixed\d+x\d+", token)
        ):
            result.append(names.setdefault(token, f"IDENT_{len(names)}"))
        else:
            result.append(token)
    return result


class Components:
    def __init__(self, identities: set[str]) -> None:
        self.parent = {i: i for i in identities}

    def find(self, node: str) -> str:
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, a: str, b: str) -> None:
        a, b = sorted((self.find(a), self.find(b)))
        self.parent[b] = a


@dataclass
class Unit:
    identity: str
    name: str
    token_count: int
    grams: frozenset[str]


def near_clone_pairs(
    units: list[Unit], threshold: float, length_ratio: float
) -> list[tuple[int, int, float]]:
    """Exact Jaccard with a lossless globally ordered prefix index (no MinHash)."""
    frequencies = Counter(g for unit in units for g in unit.grams)
    index: dict[str, list[int]] = defaultdict(list)
    result: list[tuple[int, int, float]] = []
    for i, unit in enumerate(tqdm(units, desc="Exact near-clone comparisons", mininterval=5)):
        grams = sorted(unit.grams, key=lambda g: (frequencies[g], g))
        prefix = grams[: len(grams) - math.ceil(threshold * len(grams)) + 1]
        candidates = {j for gram in prefix for j in index[gram]}
        for j in sorted(candidates):
            other = units[j]
            if unit.identity == other.identity:
                continue
            if min(unit.token_count, other.token_count) < length_ratio * max(
                unit.token_count, other.token_count
            ):
                continue
            if min(len(unit.grams), len(other.grams)) < threshold * max(
                len(unit.grams), len(other.grams)
            ):
                continue
            shared = len(unit.grams & other.grams)
            total = len(unit.grams) + len(other.grams) - shared
            if total and shared / total >= threshold:
                result.append((j, i, shared / total))
        for gram in prefix:
            index[gram].append(i)
    return result


def build_groups(
    artifacts: list[Artifact], queries: list[CandidateQuery], config: DataConfig
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    aliases: dict[str, list[Artifact]] = defaultdict(list)
    for artifact in artifacts:
        if artifact.code_identity_sha256:
            aliases[artifact.code_identity_sha256].append(artifact)
    active = {q.code_identity_sha256 for q in queries}
    active |= {i for i, arts in aliases.items() if any(a.role != "development" for a in arts)}
    components = Components(active)
    edges: list[dict[str, object]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def connect(a: str, b: str, reason: str, evidence: str, score: float | None = None) -> None:
        if a == b:
            return
        a, b = sorted((a, b))
        key = (a, b, reason)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append(
            {
                "left": a,
                "right": b,
                "reason": reason,
                "evidence": evidence,
                "score": score,
                "active": True,
            }
        )
        components.union(a, b)

    projects: dict[str, str] = {}
    exact: dict[str, str] = {}
    queries_by_identity: dict[str, list[CandidateQuery]] = defaultdict(list)
    for query in queries:
        queries_by_identity[query.code_identity_sha256].append(query)
    tokens_by_id: dict[str, list[str]] = {}
    declarations_by_id = {}
    units: list[Unit] = []
    wanted_function_hashes: dict[str, set[str]] = defaultdict(set)
    for identity in tqdm(sorted(active), desc="Project and clone units", mininterval=5):
        arts = aliases[identity]
        for artifact in arts:
            for project in artifact.project_keys:
                connect(
                    identity,
                    projects.setdefault(project, identity),
                    "known_project_or_deployment",
                    project,
                )
        representative = min(arts, key=lambda a: (a.source, a.path))
        tokens = solidity_tokens(representative.code)
        tokens_by_id[identity] = tokens
        norm = skeleton(tokens)
        key = digest(norm)
        connect(identity, exact.setdefault(key, identity), "full_source_skeleton", key)
        if len(norm) >= config.near_clone_min_tokens:
            units.append(
                Unit(
                    identity,
                    "FILE",
                    len(norm),
                    frozenset("\x1f".join(norm[j : j + 5]) for j in range(len(norm) - 4)),
                )
            )
        try:
            _, _, ds = declarations(representative.code)
        except ValueError:
            ds = []
        declarations_by_id[identity] = ds
        for q in queries_by_identity[identity]:
            part = tokens[q.scope.start_token : q.scope.end_token + 1]
            normalized = skeleton(part)
            if q.scope.kind == "FUNCTION" and len(normalized) >= config.function_clone_min_tokens:
                wanted_function_hashes[digest(normalized)].add(identity)
            if q.scope.kind == "CONTRACT" and len(normalized) >= config.near_clone_min_tokens:
                unit = Unit(
                    identity,
                    q.scope.name,
                    len(normalized),
                    frozenset(
                        "\x1f".join(normalized[j : j + 5]) for j in range(len(normalized) - 4)
                    ),
                )
                if not any(u.identity == identity and u.name == unit.name for u in units):
                    units.append(unit)
    # Index inactive declarations too, without joining unrelated selected contexts
    # through a shared dependency that occurs only outside those contexts.
    for identity in tqdm(
        sorted(aliases), desc="Raw declaration contamination index", mininterval=5
    ):
        if identity in active:
            tokens, ds = tokens_by_id[identity], declarations_by_id[identity]
        else:
            representative = min(aliases[identity], key=lambda a: (a.source, a.path))
            try:
                tokens, _, ds = declarations(representative.code)
            except ValueError:
                tokens, ds = solidity_tokens(representative.code), []
            key = digest(skeleton(tokens))
            other = exact.setdefault(key, identity)
            if other != identity:
                edges.append(
                    {
                        "left": min(identity, other),
                        "right": max(identity, other),
                        "reason": "full_source_skeleton",
                        "evidence": key,
                        "score": None,
                        "active": False,
                        "inactive_reason": "source_not_a_selected_or_protected_context",
                    }
                )
        for declaration in ds:
            if declaration.kind != "FUNCTION":
                continue
            normalized = skeleton(tokens[declaration.start : declaration.end + 1])
            if len(normalized) < config.function_clone_min_tokens:
                continue
            key = digest(normalized)
            for other in sorted(wanted_function_hashes.get(key, set())):
                if identity in active:
                    connect(identity, other, "assessed_function_clone", key)
                else:
                    edges.append(
                        {
                            "left": min(identity, other),
                            "right": max(identity, other),
                            "reason": "assessed_function_clone",
                            "evidence": key,
                            "score": None,
                            "active": False,
                            "inactive_reason": "source_not_a_selected_or_protected_context",
                        }
                    )
    for left, right, score in near_clone_pairs(
        units, config.near_clone_jaccard, config.near_clone_length_ratio
    ):
        connect(
            units[left].identity,
            units[right].identity,
            "near_clone",
            f"{units[left].name}|{units[right].name}",
            score,
        )
    members: dict[str, list[str]] = defaultdict(list)
    for identity in sorted(active):
        members[components.find(identity)].append(identity)
    groups: list[dict[str, object]] = []
    memberships = {}
    for identities in sorted(members.values()):
        group_id = digest(identities)
        roles = {a.role for i in identities for a in aliases[i]}
        role = (
            "smartbugs_external"
            if "smartbugs_external" in roles
            else "forge_external"
            if "forge_external" in roles
            else "development"
        )
        groups.append(
            {
                "group_id": group_id,
                "code_identities": identities,
                "role": role,
                "known_project_keys": sorted(
                    {k for i in identities for a in aliases[i] for k in a.project_keys}
                ),
                "project_independence_verified": False,
            }
        )
        for identity in identities:
            memberships[identity] = (group_id, role)
    for query in queries:
        query.group_id, query.role = memberships[query.code_identity_sha256]
        if query.role != "development":
            query.review_required = sorted(
                set(query.review_required) | {"protected_external_group"}
            )
    return groups, sorted(edges, key=lambda e: (e["left"], e["right"], e["reason"]))
