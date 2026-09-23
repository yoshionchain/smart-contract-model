from pathlib import Path

import pytest
from openpyxl import Workbook

from audit_distill.data.projects import group_directories, load_project_groups, repository_keys


@pytest.mark.parametrize(
    "link,expected",
    [
        ("https://github.com/Owner/Repo/tree/abcd", ["github.com/owner/repo"]),
        ("https://github.com/Owner/Repo.git", ["github.com/owner/repo"]),
        ("https://raw.githubusercontent.com/Owner/Repo/master/f.sol", ["github.com/owner/repo"]),
        ("GitHub - Owner/Repo at abcdef", ["github.com/owner/repo"]),
        ("Repo at hash · Owner/Repo (github.com)", ["github.com/owner/repo"]),
        (
            "https://github.com/Owner/A\\nhttps://github.com/Owner/B/tree/hash",
            ["github.com/owner/a", "github.com/owner/b"],
        ),
        ("https://etherscan.io/\\naddress/0x" + "a" * 40, ["etherscan.io/address/0x" + "a" * 40]),
        ("https://etherscan.io/token/0x" + "a" * 40, ["etherscan.io/address/0x" + "a" * 40]),
        ("https://github.com/organization/", []),
    ],
)
def test_repository_identity(link: str, expected: list[str]) -> None:
    assert repository_keys(link) == expected
    assert repository_keys(link.replace("\\n", "\n")) == expected


def test_transitive_multi_repository_groups() -> None:
    references = {
        "audit-c": ["repo-2"],
        "audit-a": ["repo-1"],
        "audit-b": ["repo-1", "repo-2"],
        "audit-d": [],
    }
    groups = group_directories(references)
    assert groups["audit-a"] == groups["audit-b"] == groups["audit-c"]
    assert groups["audit-d"] != groups["audit-a"]
    assert group_directories(dict(reversed(list(references.items())))) == groups


def test_workbook_mapping_and_explicit_alias(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(
        ["File Name", "Audit Company", "Project Name", "Audit Report Link", "Code Repository"]
    )
    sheet.append(["audit_a", "Auditor", "Project", "unused.pdf", "https://github.com/o/r/tree/old"])
    sheet.append(["audit-b", "Other", "Project", "unused.pdf", "https://github.com/o/r/tree/new"])
    workbook.save(tmp_path / "Audit_and_Repository_link.xlsx")
    for name in ("audit-a", "audit-b"):
        (tmp_path / "DAppSCAN-source/contracts" / name).mkdir(parents=True)
    groups, metadata = load_project_groups(tmp_path, {"audit-a": "audit_a"})
    assert groups["audit-a"] == groups["audit-b"]
    assert metadata["project_groups"] == 1
    with pytest.raises(ValueError, match="No project workbook mapping"):
        load_project_groups(tmp_path, {})
