"""Map audit directories to connected groups of shared upstream repositories.

The pinned upstream workbook is metadata, not audit-report content. An audit can
reference several repositories; sharing any one joins both complete directories.
No name-similarity or code-similarity heuristics are used.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

from openpyxl import load_workbook


def repository_keys(value: str) -> list[str]:
    # Upstream uses literal '\n' both between URLs and inside wrapped URLs.
    text = re.sub(r"(?:\\n|\r?\n)(?!https?://)", "", value).replace("\\n", " ")
    keys: set[str] = set()
    for match in re.finditer(r"https?://[^\s;,\[\]<>]+", text):
        url = urlsplit(match[0])
        host = (url.hostname or "").lower()
        parts = url.path.strip("/").split("/")
        if host in {"github.com", "www.github.com", "raw.githubusercontent.com"}:
            if len(parts) >= 2:
                keys.add("github.com/" + "/".join(parts[:2]).removesuffix(".git").lower())
        elif host == "gitlab.com":
            # This pinned dataset uses two-segment GitLab namespaces.
            if len(parts) >= 2:
                keys.add("gitlab.com/" + "/".join(parts[:2]).removesuffix(".git").lower())
        elif "scan." in host:
            address = re.search(r"/(?:address|token)/(0x[0-9a-fA-F]{40})", url.path)
            if address:
                keys.add(f"{host}/address/{address[1].lower()}")
            elif host == "tronscan.org":
                contract = re.search(r"/contract/([A-Za-z0-9]+)", url.fragment)
                if contract:
                    keys.add(f"{host}/contract/{contract[1]}")
    # Two upstream cells contain link titles rather than URLs.
    title = re.search(r"GitHub\s*-\s*([\w.-]+/[\w.-]+)", text, re.I)
    if title:
        keys.add("github.com/" + title[1].removesuffix(".git").lower())
    browser_title = re.search(r"·\s*([\w.-]+/[\w.-]+)\s*\(github.com\)", text, re.I)
    if browser_title:
        keys.add("github.com/" + browser_title[1].removesuffix(".git").lower())
    if "Etherscan" in text:
        address = re.search(r"\b0x[0-9a-fA-F]{40}\b", text)
        if address:
            keys.add(f"etherscan.io/address/{address[0].lower()}")
    return sorted(keys)


def group_directories(references: dict[str, list[str]]) -> dict[str, str]:
    parent = {name: name for name in references}

    def find(name: str) -> str:
        while name != parent[name]:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    first: dict[str, str] = {}
    for directory, keys in sorted(references.items()):
        for key in keys:
            previous = first.setdefault(key, directory)
            left, right = sorted((find(directory), find(previous)))
            parent[right] = left
    return {name: f"dappscan:{find(name)}" for name in sorted(references)}


def load_project_groups(
    root: Path,
    aliases: dict[str, str],
) -> tuple[dict[str, str], dict[str, object]]:
    workbook = load_workbook(
        root / "Audit_and_Repository_link.xlsx", read_only=True, data_only=True
    )
    try:
        sheet = workbook.active
        if sheet is None:
            raise ValueError("DAppSCAN project workbook has no active sheet")
        rows = iter(sheet.values)
        header = next(rows)
        if header[:5] != (
            "File Name",
            "Audit Company",
            "Project Name",
            "Audit Report Link",
            "Code Repository",
        ):
            raise ValueError("Unexpected DAppSCAN project workbook columns")
        lookup: dict[str, str] = {}
        for row in rows:
            if not isinstance(row[0], str) or not isinstance(row[4], str):
                raise ValueError("Missing directory/repository metadata in DAppSCAN workbook")
            if row[0] in lookup:
                raise ValueError(f"Duplicate project metadata: {row[0]}")
            lookup[row[0]] = row[4]
    finally:
        workbook.close()
    directories = sorted(
        path.name for path in (root / "DAppSCAN-source/contracts").iterdir() if path.is_dir()
    )
    references: dict[str, list[str]] = {}
    mapping_rows: dict[str, object] = {}
    for directory in directories:
        key = aliases.get(directory, directory)
        if key not in lookup:
            raise ValueError(f"No project workbook mapping for {directory}")
        references[directory] = repository_keys(lookup[key])
        mapping_rows[directory] = {
            "workbook_directory": key,
            "repository_keys": references[directory],
            "directory_fallback": not references[directory],
        }
    groups = group_directories(references)
    return groups, {
        "strategy": "shared_upstream_repository",
        "audit_directories": len(directories),
        "project_groups": len(set(groups.values())),
        "directory_to_project": groups,
        "directory_metadata": mapping_rows,
        "directory_fallbacks": [name for name, keys in references.items() if not keys],
    }
