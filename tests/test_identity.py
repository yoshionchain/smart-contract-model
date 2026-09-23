import pytest

from audit_distill.data.identity import code_identity
from audit_distill.data.line_numbers import render_line_numbers
from audit_distill.data.normalize import sha256_text, source_hash


@pytest.mark.parametrize(
    "first,second",
    [
        ("a + + b", "a ++ b"),
        ("a b", "ab"),
        ("a >> = b", "a >>= b"),
        ('"a b"', '"ab"'),
        ('"// hint"', '"// other"'),
        ('unicode"Café"', 'unicode"Cafe\u0301"'),
        ("1e+2", "1 e + 2"),
        ('"a\\"b"', '"ab"'),
    ],
)
def test_lexical_boundaries_and_literals_remain_distinct(first: str, second: str) -> None:
    assert code_identity(first) != code_identity(second)


def test_line_sensitive_cache_hash_changes_even_when_other_hashes_match() -> None:
    first, second = "contract A{}\n", "\ncontract A{}\n"
    assert code_identity(first) == code_identity(second)
    assert source_hash(first) == source_hash(second)
    assert sha256_text(render_line_numbers(first)) != sha256_text(render_line_numbers(second))


@pytest.mark.parametrize("code", ["/* unclosed", '"unclosed', "// comment only", " \n"])
def test_invalid_identity_is_logged(code: str) -> None:
    with pytest.raises(ValueError):
        code_identity(code)


def test_source_hash_preserves_unicode_literal_spelling() -> None:
    assert source_hash('"Café"') != source_hash('"Cafe\u0301"')
