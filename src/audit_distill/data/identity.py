"""Exact lexical identity, independent of comments and layout (not semantic deduplication)."""

import hashlib
import json
import re

# Longest match matters: `a + +b` and `a++ + b` must not share a fingerprint.
TOKEN = re.compile(
    r"0[xX][0-9a-fA-F_]+"
    r"|(?:[0-9][0-9_]*(?:\.[0-9_]+)?|\.[0-9_]+)(?:[eE][+-]?[0-9][0-9_]*)?"
    r"|(?:[^\W\d]|\$)[\w$]*"
    r"|>>>=|>>>|>>=|<<=|\*\*|\+\+|--|&&|\|\||<=|>=|==|!=|\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<|>>|=>|:=|->"
    r"|[^\s]"
)


def solidity_tokens(code: str) -> list[str]:
    """Retain literal spellings, operators and token boundaries exactly.

    This lexer does not compile or type-check Solidity. Unterminated literals and
    block comments fail closed rather than receiving an unreliable identity.
    Unicode is not normalized inside literals: that can change their values.
    """
    tokens: list[str] = []
    index = 0
    while index < len(code):
        if code[index].isspace():
            index += 1
        elif code.startswith("//", index):
            index += 2
            while index < len(code) and code[index] not in "\r\n":
                index += 1
        elif code.startswith("/*", index):
            end = code.find("*/", index + 2)
            if end < 0:
                raise ValueError("Unterminated block comment")
            index = end + 2
        elif code[index] in {'"', "'"}:
            start, quote = index, code[index]
            index += 1
            while index < len(code):
                if code[index] == "\\":
                    index += 2
                elif code[index] == quote:
                    index += 1
                    tokens.append(code[start:index])
                    break
                else:
                    index += 1
            else:
                raise ValueError("Unterminated string literal")
        else:
            token = TOKEN.match(code, index)
            if token is None:
                raise ValueError(f"Cannot tokenize source at offset {index}")
            tokens.append(token[0])
            index = token.end()
    return tokens


def code_identity(code: str) -> str:
    tokens = solidity_tokens(code)
    if not tokens:
        raise ValueError("Source contains no code tokens")
    # JSON array encoding retains boundaries; joining spellings would introduce collisions.
    serialized = json.dumps(tokens, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
