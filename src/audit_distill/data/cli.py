"""Build the reentrancy dataset without teacher generation or training."""

import argparse
import logging
from pathlib import Path

from audit_distill.data.inventory import build_inventory
from audit_distill.data.release import build_release, load_release_config
from audit_distill.data.settings import load_data_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/project.yaml"))
    parser.add_argument("--release-config", type=Path, default=Path("configs/release.yaml"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--stage",
        choices=["inventory", "release"],
        default="inventory",
        help=(
            "inventory: candidates from all pinned sources (minutes); release: balanced "
            "train/validation/test cohorts from the inventory (seconds)"
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.stage == "inventory":
            config = load_data_config(args.config)
            if args.output_dir:
                config = config.model_copy(update={"output_dir": args.output_dir.resolve()})
            build_inventory(config, args.config.resolve().parent.parent)
        else:
            release = load_release_config(args.release_config)
            if args.output_dir:
                release = release.model_copy(update={"output_dir": args.output_dir.resolve()})
            build_release(release, args.release_config.resolve().parent.parent)
    except (ValueError, OSError) as error:
        logging.error("Dataset build stopped: %s", error)
        raise SystemExit(1) from error
