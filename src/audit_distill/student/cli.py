"""Build the student SFT and evaluation datasets; no model calls."""

import argparse
import logging
from pathlib import Path

from audit_distill.student.dataset import build_student_data, load_student_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/student.yaml"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = args.config.resolve().parent.parent
    try:
        manifest = build_student_data(*load_student_config(args.config, root), root)
    except (ValueError, OSError) as error:
        logging.error("Student dataset build stopped: %s", error)
        raise SystemExit(1) from error
    logging.info("Student data %s: %s", manifest["student_content_sha256"], manifest["counts"])
