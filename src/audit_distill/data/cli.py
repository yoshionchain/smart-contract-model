"""Build the reentrancy dataset from the pinned benchmark; no model calls."""

import argparse
import logging
from pathlib import Path

from audit_distill.data.release import build_release
from audit_distill.data.settings import load_data_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/data.yaml"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        manifest = build_release(load_data_config(args.config), args.config.resolve().parent.parent)
    except (ValueError, OSError) as error:
        logging.error("Dataset build stopped: %s", error)
        raise SystemExit(1) from error
    logging.info("Release %s: %s", manifest["release_content_sha256"], manifest["counts"])
