"""Generate label-blind teacher reports; `--dry-run` makes no model call."""

import argparse
import json
import logging
from pathlib import Path

from audit_distill.teacher.generate import TeacherStopped, generate, load_teacher_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/teacher.yaml"))
    parser.add_argument("--split", choices=["train", "validation", "test"], required=True)
    parser.add_argument("--pilot", action="store_true", help="a few training queries only")
    parser.add_argument(
        "--ceiling", action="store_true", help="the one approved test run (ceiling row)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="counts, prompts and estimates; no model call"
    )
    parser.add_argument(
        "--max-invocations", type=int, help="hard cap on Codex calls in this session"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = args.config.resolve().parent.parent
    try:
        config, tokenizer = load_teacher_config(args.config, root)
        summary = generate(
            config,
            tokenizer,
            root,
            args.split,
            pilot=args.pilot,
            ceiling=args.ceiling,
            dry=args.dry_run,
            max_invocations=args.max_invocations,
        )
    except TeacherStopped as stopped:
        logging.error("Teacher run stopped; valid work is saved and resumes: %s", stopped)
        raise SystemExit(2) from stopped
    except (ValueError, OSError) as error:
        logging.error("Teacher run failed: %s", error)
        raise SystemExit(1) from error
    print(json.dumps(summary, indent=2, ensure_ascii=False))
