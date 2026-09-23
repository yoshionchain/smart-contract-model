"""Fetch immutable upstream revisions; never reset an existing user's checkout."""

import argparse
import logging
import subprocess
from pathlib import Path

from audit_distill.config import Upstream
from audit_distill.provenance import git_output

logger = logging.getLogger(__name__)


def verify_checkout(upstream: Upstream) -> dict[str, str]:
    if not (upstream.path / ".git").exists():
        raise ValueError(f"Missing Git checkout: {upstream.path}; run scripts/fetch_data.py")
    revision = git_output(upstream.path, "rev-parse", "HEAD")
    if revision != upstream.revision:
        raise ValueError(f"Revision mismatch for {upstream.path}: {revision}")
    origin = git_output(upstream.path, "remote", "get-url", "origin")
    if origin.removesuffix(".git") != upstream.repository.removesuffix(".git"):
        raise ValueError(f"Unexpected repository origin for {upstream.path}")
    if git_output(upstream.path, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError(
            f"Upstream checkout is dirty: {upstream.path}; refusing unreliable provenance"
        )
    return {"repository": upstream.repository, "commit": revision}


def fetch(
    upstream: Upstream, *, dappscan: bool = False, sparse_paths: list[str] | None = None
) -> None:
    if upstream.path.exists():
        verify_checkout(upstream)
        if (
            sparse_paths is not None
            and git_output(
                upstream.path, "config", "--default", "false", "--get", "core.sparseCheckout"
            ).lower()
            == "true"
        ):
            subprocess.run(
                ["git", "-C", str(upstream.path), "sparse-checkout", "add", *sparse_paths],
                check=True,
            )
            verify_checkout(upstream)
        logger.info("Verified existing %s at %s", upstream.path, upstream.revision)
        return
    upstream.path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Fetching %s at %s", upstream.repository, upstream.revision)
    subprocess.run(["git", "init", str(upstream.path)], check=True, stdout=subprocess.DEVNULL)
    prefix = ["git", "-C", str(upstream.path)]
    subprocess.run([*prefix, "remote", "add", "origin", upstream.repository], check=True)
    if dappscan or sparse_paths is not None:
        subprocess.run([*prefix, "config", "remote.origin.promisor", "true"], check=True)
        subprocess.run(
            [*prefix, "config", "remote.origin.partialclonefilter", "blob:none"], check=True
        )
        subprocess.run(
            [
                *prefix,
                "sparse-checkout",
                "set",
                *(
                    sparse_paths
                    if sparse_paths is not None
                    else ["DAppSCAN-source/contracts", "DAppSCAN-source/SWCsource"]
                ),
            ],
            check=True,
        )
    subprocess.run(
        [*prefix, "fetch", "--depth=1", "--filter=blob:none", "origin", upstream.revision],
        check=True,
    )
    subprocess.run([*prefix, "checkout", "--detach", "FETCH_HEAD"], check=True)
    verify_checkout(upstream)


def main() -> None:
    from audit_distill.data.settings import load_data_config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/project.yaml"))
    parser.add_argument("--source", action="append", help="Fetch selected configured source(s)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_data_config(args.config)
    selected = args.source or list(config.datasets)
    for name in selected:
        if name not in config.datasets:
            parser.error(f"Unknown source: {name}")
        source = config.datasets[name]
        fetch(source, sparse_paths=source.sparse_paths)
