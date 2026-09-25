"""Leakage groups: exact token skeletons, near clones and declared families (union-find)."""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from tqdm import tqdm

from audit_distill.data.identity import solidity_tokens
from audit_distill.provenance import digest

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


def group_contracts(
    codes: dict[str, str],
    families: dict[str, str],
    *,
    min_tokens: int,
    jaccard: float,
    length_ratio: float,
) -> tuple[dict[str, str], list[dict[str, object]]]:
    """Group IDs per contract key; contracts sharing a family, skeleton or near clone join.

    `codes` maps a contract key to comment-blanked source; `families` maps keys to a
    declared family (e.g. an RSD scenario). Returns the group map and the union edges.
    """
    components = Components(set(codes))
    edges: list[dict[str, object]] = []

    def connect(a: str, b: str, reason: str, score: float | None = None) -> None:
        if a != b and components.find(a) != components.find(b):
            edges.append({"left": min(a, b), "right": max(a, b), "reason": reason, "score": score})
            components.union(a, b)

    first: dict[str, str] = {}
    units: list[Unit] = []
    for key in sorted(codes):
        if key in families:
            connect(key, first.setdefault(f"family:{families[key]}", key), "declared_family")
        norm = skeleton(solidity_tokens(codes[key]))
        connect(key, first.setdefault(f"skeleton:{digest(norm)}", key), "exact_skeleton")
        if len(norm) >= min_tokens:
            grams = frozenset("\x1f".join(norm[j : j + 5]) for j in range(len(norm) - 4))
            units.append(Unit(key, "FILE", len(norm), grams))
    for left, right, score in near_clone_pairs(units, jaccard, length_ratio):
        connect(units[left].identity, units[right].identity, "near_clone", round(score, 4))
    members: dict[str, list[str]] = defaultdict(list)
    for key in sorted(codes):
        members[components.find(key)].append(key)
    groups = {key: digest(keys) for keys in members.values() for key in keys}
    return groups, edges
