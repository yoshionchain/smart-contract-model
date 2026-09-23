"""Normalization is exclusively a hash operation, never a source rewrite."""

import hashlib


def normalize_for_hash(code: str) -> str:
    text = code.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_hash(code: str) -> str:
    return sha256_text(normalize_for_hash(code))
