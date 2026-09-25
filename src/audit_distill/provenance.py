"""Inspect source revisions and record the environment without secrets."""

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path


def git_output(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    """Deterministic SHA-256 of a JSON value (sorted keys, compact, UTF-8)."""
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def project_provenance(root: Path) -> dict[str, object]:
    try:
        commit: str | None = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        commit = None  # A new, not-yet-committed repository has no revision.
    tracked_inputs = sorted(
        [
            *root.glob("src/**/*.py"),
            *root.glob("scripts/*.py"),
            *root.glob("configs/**/*.yaml"),
            *root.glob("configs/prompts/*.txt"),
            *root.glob("schemas/**/*.json"),
            root / "pyproject.toml",
            root / "uv.lock",
            root / "SPEC.md",
        ]
    )
    return {
        "git_commit": commit,
        "git_dirty": bool(git_output(root, "status", "--porcelain")),
        "python_version": platform.python_version(),
        "package_versions": dict(
            sorted(
                (dist.metadata["Name"], dist.version)
                for dist in importlib.metadata.distributions()
                if dist.metadata["Name"]
            )
        ),
        "input_file_hashes": {
            str(path.relative_to(root)): file_sha256(path)
            for path in tracked_inputs
            if path.is_file()
        },
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
