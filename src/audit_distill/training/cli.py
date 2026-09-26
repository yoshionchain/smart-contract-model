"""Fine-tune one student condition with LoRA; `--smoke` runs a tiny CPU check."""

import argparse
import logging
from pathlib import Path

from audit_distill.training.train import load_training_config, train

CONDITIONS = {"label": "label", "report": "report", "report-vf": "report_vf", "multi": "multi"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/training.yaml"))
    parser.add_argument("--condition", choices=list(CONDITIONS), required=True)
    parser.add_argument(
        "--smoke", action="store_true", help="tiny random model on a few examples (not a result)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = args.config.resolve().parent.parent
    try:
        selection = train(
            CONDITIONS[args.condition], load_training_config(args.config, root), root, args.smoke
        )
    except (ValueError, OSError) as error:
        logging.error("Training stopped: %s", error)
        raise SystemExit(1) from error
    logging.info("Best epoch %s: %s", selection["best_epoch"], selection["epochs"])
