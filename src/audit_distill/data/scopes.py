"""Conservative lexical declaration resolution; never a compiler or type checker.

Only uniquely resolved declarations are returned. Inheritance and semantic input
sufficiency remain explicit review items, including when resolution succeeds.
"""

import bisect
import hashlib
import json
import re
from dataclasses import dataclass

from audit_distill.data.comments import strip_comments
from audit_distill.data.identity import solidity_tokens
from audit_distill.data.records import Scope


@dataclass(frozen=True)
class Declaration:
    kind: str
    contract: str
    name: str
    signature: str
    start: int
    end: int


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def declarations(code: str) -> tuple[list[str], list[tuple[int, int]], list[Declaration]]:
    clean = strip_comments(code)
    tokens = solidity_tokens(clean)
    spans: list[tuple[int, int]] = []
    cursor = 0
    for token in tokens:
        start = clean.find(token, cursor)
        if start < 0:
            raise ValueError("Token coordinates could not be resolved")
        cursor = start + len(token)
        spans.append((start, cursor))
    stack: list[int] = []
    pairs: dict[int, int] = {}
    depth: list[int] = []
    for i, token in enumerate(tokens):
        depth.append(len(stack))
        if token in {"{", "(", "["}:
            stack.append(i)
        elif token in {"}", ")", "]"}:
            if not stack or tokens[stack[-1]] != {"}": "{", ")": "(", "]": "["}[token]:
                raise ValueError("Unbalanced Solidity delimiters")
            pairs[stack.pop()] = i
    if stack:
        raise ValueError("Unbalanced Solidity delimiters")
    result: list[Declaration] = []
    for i, token in enumerate(tokens[:-1]):
        if token not in {"contract", "interface", "library"} or depth[i] != 0:
            continue
        name = tokens[i + 1]
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", name):
            raise ValueError("Unresolved contract declaration")
        body = i + 2
        while body < len(tokens) and tokens[body] not in {"{", ";"}:
            body += 1
        if body not in pairs or tokens[body] != "{":
            raise ValueError("Missing contract body")
        end = pairs[body]
        result.append(Declaration("CONTRACT", name, name, name, i, end))
        for j in range(body + 1, end):
            if depth[j] != 1 or tokens[j] not in {"function", "constructor", "fallback", "receive"}:
                continue
            p = j + 1
            fn = tokens[j]
            if fn == "function":
                fn = "fallback" if tokens[p] == "(" else tokens[p]
                if tokens[p] != "(":
                    p += 1
            if tokens[p] != "(" or p not in pairs:
                continue
            close = pairs[p]
            tail = close + 1
            while tail < end and tokens[tail] not in {"{", ";"}:
                if tokens[tail] in {"(", "["}:
                    tail = pairs[tail]
                tail += 1
            if tail >= end:
                raise ValueError("Unresolved function body")
            # An unnamed function-typed state variable is not a fallback declaration.
            if fn == "fallback" and tokens[tail] == ";":
                continue
            last = pairs[tail] if tokens[tail] == "{" else tail
            signature = f"{fn}({' '.join(tokens[p + 1 : close])})"
            result.append(Declaration("FUNCTION", name, fn, signature, j, last))
    return tokens, spans, result


def resolve_scope(code: str, kind: str, native: str) -> Scope:
    tokens, spans, units = declarations(code)
    if not tokens:
        raise ValueError("Empty source")
    if kind == "FILE":
        start, end, name = 0, len(tokens) - 1, "FILE"
    else:
        native = native.strip()
        contract, _, fn = native.replace("::", ".").rpartition(".")
        if kind == "CONTRACT":
            matches = [d for d in units if d.kind == kind and d.name == native]
        else:
            if not contract:
                fn = native
            bare = fn.split("(", 1)[0]
            matches = [
                d
                for d in units
                if d.kind == kind and d.name == bare and (not contract or d.contract == contract)
            ]
            if "(" in fn:
                exact = re.sub(r"\s+", "", fn)
                matches = [d for d in matches if re.sub(r"\s+", "", d.signature) == exact]
        if len(matches) != 1:
            raise ValueError(f"Unresolved or ambiguous {kind.lower()} scope: {native}")
        unit = matches[0]
        start, end = unit.start, unit.end
        name = unit.contract if kind == "CONTRACT" else f"{unit.contract}.{unit.signature}"
    newlines = [m.end() for m in re.finditer(r"\r\n|\r|\n", code)]
    return Scope(
        kind=kind,
        name=name,
        start_line=bisect.bisect_right(newlines, spans[start][0]) + 1,
        end_line=bisect.bisect_right(newlines, spans[end][1] - 1) + 1,
        start_token=start,
        end_token=end,
        token_identity=digest([kind, start, end, tokens[start : end + 1]]),
    )
