"""Build the reentrancy dataset stages without teacher generation or training."""

import argparse
import logging
from pathlib import Path

from audit_distill.data.freeze import freeze
from audit_distill.data.inventory import build_inventory
from audit_distill.data.release import build_release, load_release_config
from audit_distill.data.settings import load_data_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/project.yaml"))
    parser.add_argument("--release-config", type=Path, default=Path("configs/release.yaml"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reviews", type=Path, default=Path("data/reviews/reentrancy-v2.2.jsonl"))
    parser.add_argument(
        "--stage",
        choices=["inventory", "split", "freeze"],
        default="inventory",
        help=(
            "inventory: v2.1 candidate baseline; split: v2.2 balanced split and review "
            "queues; freeze: apply completed human reviews and write the frozen cohorts"
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
            root = args.release_config.resolve().parent.parent
            if args.stage == "split":
                build_release(release, root)
            else:
                freeze(release, args.reviews, root)
    except (ValueError, OSError) as error:
        logging.error("Dataset build stopped: %s", error)
        raise SystemExit(1) from error
