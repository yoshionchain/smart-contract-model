from audit_distill.data.line_numbers import render_line_numbers, source_lines
from audit_distill.data.normalize import source_hash


def test_hash_normalization_preserves_source() -> None:
    first = "\r\ncontract Café {  \r\n}\t\r\n"
    second = "contract Café {\n}\n\n"
    assert source_hash(first) == source_hash(second)
    assert first.startswith("\r\n")


def test_line_number_semantics() -> None:
    code = "\r\npragma solidity ^0.4.24;\r\n\r\ncontract A {}\n"
    assert source_lines(code) == ["", "pragma solidity ^0.4.24;", "", "contract A {}"]
    assert render_line_numbers(code) == (
        "0001 |\n0002 | pragma solidity ^0.4.24;\n0003 |\n0004 | contract A {}"
    )
    assert render_line_numbers("a\n\n") == "0001 | a\n0002 |"
    assert render_line_numbers("") == ""
    assert source_lines("a\u2028b\n") == ["a\u2028b"]
