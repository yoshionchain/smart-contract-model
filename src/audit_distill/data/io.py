"""Contain upstream source references within the pinned checkout."""

from pathlib import Path, PurePosixPath


def contained_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"Unsafe upstream path: {relative}")
    result = root / relative
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Upstream path escapes dataset: {relative}")
    return result
