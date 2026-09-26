"""Evaluation entry points: `predict` (GPU; `--smoke` on CPU) and `evaluate` (CPU)."""

import argparse
import logging
from pathlib import Path

from audit_distill.evaluation.predict import load_evaluation_config, predict
from audit_distill.evaluation.score import evaluate


def parser(description: str) -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=description)
    result.add_argument("--config", type=Path, default=Path("configs/evaluation.yaml"))
    result.add_argument("--split", choices=["validation", "test"], default="test")
    return result


def predict_main() -> None:
    args_parser = parser("Greedy predictions for every mode on one split (GPU).")
    args_parser.add_argument("--smoke", action="store_true", help="tiny model on CPU; not a result")
    args = args_parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = args.config.resolve().parent.parent
    try:
        manifest = predict(load_evaluation_config(args.config, root), root, args.split, args.smoke)
    except (ValueError, OSError) as error:
        logging.error("Prediction stopped: %s", error)
        raise SystemExit(1) from error
    logging.info("Predictions written: %s", sorted(manifest["modes"]))


def evaluate_main() -> None:
    args = parser("Score all modes, baselines and the teacher ceiling (CPU).").parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = args.config.resolve().parent.parent
    try:
        results = evaluate(load_evaluation_config(args.config, root), root, args.split)
    except (ValueError, OSError) as error:
        logging.error("Evaluation stopped: %s", error)
        raise SystemExit(1) from error
    for name, entry in results["modes"].items():
        logging.info("%-20s macro-F1 %.3f (invalid %s)", name, entry["macro_f1"], entry["invalid"])
