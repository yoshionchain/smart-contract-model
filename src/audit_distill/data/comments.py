"""A small Solidity comment lexer that leaves quoted literals and code untouched."""

from collections.abc import Iterator


def comment_spans(code: str) -> Iterator[tuple[int, int]]:
    index = 0
    while index < len(code):
        char = code[index]
        if char in {"'", '"'}:
            quote = char
            index += 1
            while index < len(code):
                if code[index] == "\\":
                    index += 2
                elif code[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
        elif code.startswith("//", index):
            start = index
            while index < len(code) and code[index] not in "\r\n":
                index += 1
            yield start, index
        elif code.startswith("/*", index):
            end = code.find("*/", index + 2)
            if end == -1:
                raise ValueError("Unterminated Solidity block comment")
            yield index, end + 2
            index = end + 2
        else:
            index += 1


def blank_spans(code: str, spans: list[tuple[int, int]]) -> str:
    characters = list(code)
    for start, end in spans:
        for index in range(start, end):
            if characters[index] not in "\r\n":
                characters[index] = " "
    return "".join(characters)


def strip_comments(code: str) -> str:
    """Approved rule: blank every comment, including informal answer hints."""
    return blank_spans(code, list(comment_spans(code)))
