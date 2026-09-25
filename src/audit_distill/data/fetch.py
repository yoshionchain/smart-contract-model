"""Fetch the pinned benchmark revision; never reset an existing checkout."""

import argparse
import logging
import subprocess
from pathlib import Path

from audit_distill.data.settings import Source, load_data_config
from audit_distill.provenance import git_output

logger = logging.getLogger(__name__)


def verify_checkout(source: Source) -> dict[str, str]:
    if not (source.path / ".git").exists():
        raise ValueError(f"Missing Git checkout: {source.path}; run scripts/fetch_data.py")
    revision = git_output(source.path, "rev-parse", "HEAD")
    if revision != source.revision:
        raise ValueError(f"Revision mismatch for {source.path}: {revision}")
    origin = git_output(source.path, "remote", "get-url", "origin")
    if origin.removesuffix(".git") != source.repository.removesuffix(".git"):
        raise ValueError(f"Unexpected repository origin for {source.path}")
    if git_output(source.path, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError(f"Checkout is dirty: {source.path}; refusing unreliable provenance")
    return {"repository": source.repository, "commit": revision}


def fetch(source: Source) -> None:
    if source.path.exists():
        verify_checkout(source)
        logger.info("Verified existing %s at %s", source.path, source.revision)
        return
    source.path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Fetching %s at %s", source.repository, source.revision)
    git = ["git", "-C", str(source.path)]
    subprocess.run(["git", "init", "-q", str(source.path)], check=True)
    subprocess.run([*git, "remote", "add", "origin", source.repository], check=True)
    subprocess.run([*git, "sparse-checkout", "set", *source.sparse_paths], check=True)
    subprocess.run([*git, "fetch", "-q", "--depth=1", "origin", source.revision], check=True)
    subprocess.run([*git, "checkout", "-q", "--detach", "FETCH_HEAD"], check=True)
    verify_checkout(source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/data.yaml"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    fetch(load_data_config(args.config).source)
