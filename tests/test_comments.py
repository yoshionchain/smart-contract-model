from audit_distill.data.comments import (
    blank_spans,
    comment_spans,
    strip_comments,
)


def test_comment_lexer_preserves_strings_code_and_positions() -> None:
    code = (
        "/* @source: SWC-101\r\n @vulnerable_at_lines: 3 */\r\n"
        'string a = "https://example.com/*safe*/"; // <yes> <report>\n'
        "string b = 'escaped\\'//literal'; /*INSECURE*/ f();\n"
    )
    cleaned = blank_spans(code, list(comment_spans(code)))
    assert len(code) == len(cleaned)
    assert [i for i, c in enumerate(code) if c in "\r\n"] == [
        i for i, c in enumerate(cleaned) if c in "\r\n"
    ]
    assert '"https://example.com/*safe*/"' in cleaned
    assert "'escaped\\'//literal'" in cleaned
    assert "f();" in cleaned
    assert not list(comment_spans(cleaned))


def test_uniform_policy_removes_ordinary_comments_and_preserves_literals() -> None:
    code = (
        "// Contract documentation\r\n"
        "/* SWC-107-Reentrancy: L4\r\n annotation continuation */\r\n"
        "f(); // SWC-104-Unchecked Call Return Value: L4\r\n"
        'string literal = "SWC-107 // not a comment";\r\n'
    )
    clean = strip_comments(code)
    assert len(clean) == len(code)
    assert [i for i, c in enumerate(code) if c in "\r\n"] == [
        i for i, c in enumerate(clean) if c in "\r\n"
    ]
    assert "Contract documentation" not in clean
    assert "annotation continuation" not in clean
    assert "f();" in clean
    assert '"SWC-107 // not a comment"' in clean
    assert strip_comments(clean) == clean


def test_smartbugs_informal_hints_removed() -> None:
    code = 'f(); // INSECURE\n/* overflow */ g();\nstring s = "/* code literal */";'
    clean = strip_comments(code)
    assert "INSECURE" not in clean
    assert "overflow" not in clean
    assert "f();" in clean and "g();" in clean
    assert '"/* code literal */"' in clean
    assert strip_comments(clean) == clean
