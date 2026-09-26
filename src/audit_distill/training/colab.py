"""Drive training on a Colab GPU VM through the `colab` CLI (google-colab-cli).

`up` rents the VM, uploads a bundle (tracked files, `.git` for provenance, the student
data and any finished conditions of the current run) and installs the locked
environment as a background job. `train` and `predict` start detached jobs on the VM
(`colab exec` calls time out; training must not); finished conditions are skipped, so a
lost VM costs at most the condition in progress. `watch` polls the VM, downloads every
newly finished condition at once, stops with an error the moment the VM is gone, and
returns when the job ends. `status`, `fetch` and `down` do what they say. Nothing here
runs without the owner's approval of the GPU job.
"""

import argparse
import json
import logging
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)
REMOTE = "/content/audit-distill"
CONDITIONS = ("label", "report", "report-vf", "multi")


class VMLost(RuntimeError):
    """The Colab session no longer exists."""


def colab(*args: str, stdin: str | None = None) -> None:
    subprocess.run(["colab", *args], input=stdin, text=True, check=True)


def remote(session: str, code: str, timeout: int) -> str:
    """Run Python on the VM kernel and return its output (raises VMLost if it is gone)."""
    result = subprocess.run(
        ["colab", "exec", "-s", session, "--timeout", str(timeout)],
        input=code,
        text=True,
        capture_output=True,
    )
    output = result.stdout + result.stderr
    if "not found" in output and "Session" in output:
        raise VMLost(f"Colab session {session!r} no longer exists")
    if result.returncode != 0:
        raise RuntimeError(f"colab exec failed: {output[-2000:]}")
    return result.stdout


def shell(commands: list[str]) -> str:
    """Python source that runs shell commands in the repo on the VM and prints output."""
    lines = ["import subprocess"]
    for command in commands:
        lines.append(
            f"print(subprocess.run(['bash', '-lc', {command!r}], cwd={REMOTE!r}, "
            "capture_output=True, text=True).stdout[-4000:], flush=True)"
        )
    return "\n".join(lines)


def run_dir(root: Path) -> str:
    """The current run's output directory (relative), from the training config."""
    config = yaml.safe_load((root / "configs/training.yaml").read_text(encoding="utf-8"))
    return str(config["output_dir"])


def finished(root: Path) -> list[Path]:
    """Local condition directories of the current run that completed (selection.json)."""
    base = root / run_dir(root)
    return sorted(p.parent for p in base.glob("*/selection.json"))


def bundle(root: Path) -> Path:
    """Tracked files, `.git`, student data and finished conditions (no raw data)."""
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout.split("\0")
    student = sorted((root / "data/processed/student").glob("*"))
    if not student:
        raise ValueError("Build the student data first (scripts/build_student_dataset.py)")
    path = Path(tempfile.mkdtemp()) / "bundle.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name in filter(None, tracked):
            archive.add(root / name, arcname=name, recursive=False)
        archive.add(root / ".git", arcname=".git")
        for file in student:
            archive.add(file, arcname=str(file.relative_to(root)))
        for condition in finished(root):
            archive.add(condition, arcname=str(condition.relative_to(root)))
    return path


def sync(session: str, root: Path) -> None:
    """Upload the current bundle and extract it over the repo on the VM (keeps `runs/`)."""
    path = bundle(root)
    logger.info("Uploading %s (%.1f MB)", path.name, path.stat().st_size / 1e6)
    colab("upload", "-s", session, str(path), "/content/bundle.tar.gz")
    extract = (
        "import tarfile, os\n"
        f"os.makedirs({REMOTE!r}, exist_ok=True)\n"
        f"tarfile.open('/content/bundle.tar.gz').extractall({REMOTE!r}, filter='data')\n"
        "print('extracted')\n"
    )
    remote(session, extract, 300)
    print(remote(session, shell(["git log --oneline -1; git status --short | head -5"]), 60))


def launch(session: str, name: str, commands: list[str]) -> None:
    """Start shell commands as a detached job on the VM; `runs/STATUS` tracks it."""
    body = "".join(f"  {c} || {{ echo FAILED {name} > runs/STATUS; exit 1; }}\n" for c in commands)
    job = (
        f"set -u\ncd {REMOTE}\nmkdir -p runs\necho RUNNING {name} > runs/STATUS\n"
        f"{{\n{body}}}\necho DONE {name} > runs/STATUS\n"
    )
    code = (
        "import subprocess, pathlib\n"
        f"path = pathlib.Path('/content') / {f'{name}_job.sh'!r}  # outside the repo\n"
        f"path.write_text({job!r})\n"
        "subprocess.Popen(['setsid', 'nohup', 'bash', str(path)], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)\n"
        "print('started', path)\n"
    )
    print(remote(session, code, 60))


def up(session: str, gpu: str, root: Path) -> None:
    colab("new", "-s", session, "--gpu", gpu)
    sync(session, root)
    launch(
        session,
        "setup",
        [
            "pip install -q uv > runs/setup.log 2>&1",
            f"git config --global --add safe.directory {REMOTE}",
            "uv sync --locked --group train >> runs/setup.log 2>&1",
            "uv run python -c 'import torch; assert torch.cuda.is_available(); "
            "print(torch.__version__, torch.cuda.get_device_name(0))' >> runs/setup.log 2>&1",
        ],
    )
    state = watch(session, root, interval=30, fetch_results=False)
    print(remote(session, shell(["tail -n 3 runs/setup.log", "git log --oneline -1"]), 60))
    if not state.startswith("DONE"):
        raise RuntimeError(f"VM setup failed: {state}")


def train(session: str, root: Path, conditions: list[str]) -> None:
    base = run_dir(root)
    launch(
        session,
        "train",
        [
            f"[ -f {base}/{c}/selection.json ] || "
            f"uv run python scripts/train.py --condition {c} > runs/train-{c}.log 2>&1"
            for c in conditions
        ],
    )


def predict(session: str) -> None:
    launch(session, "predict", ["uv run python scripts/predict.py > runs/predict.log 2>&1"])


def remote_state(session: str, root: Path) -> dict:
    code = (
        "import json, pathlib\n"
        f"repo = pathlib.Path({REMOTE!r})\n"
        "flag = repo / 'runs/STATUS'\n"
        "status = flag.read_text().strip() if flag.exists() else ''\n"
        f"base = repo / {run_dir(root)!r}\n"
        "done = sorted(p.parent.name for p in base.glob('*/selection.json'))\n"
        "print('STATE ' + json.dumps({'status': status, 'finished': done}))\n"
    )
    output = remote(session, code, 120)
    line = next(line for line in output.splitlines() if line.startswith("STATE "))
    return json.loads(line.removeprefix("STATE "))


def status(session: str) -> None:
    print(
        remote(
            session,
            shell(
                [
                    "cat runs/STATUS 2>/dev/null || echo 'no job'",
                    "for f in runs/train-*.log runs/predict.log; do [ -f $f ] || continue; "
                    'echo "== $f"; '
                    "tail -c 1500 \"$f\" | tr '\\r' '\\n' | grep -v '^\\s*$' | tail -4; done",
                    "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader",
                ]
            ),
            120,
        )
    )


def fetch(session: str, root: Path) -> None:
    remote(session, shell(["tar czf /content/runs.tar.gz --exclude=checkpoints runs"]), 900)
    local = Path(tempfile.mkdtemp()) / "runs.tar.gz"
    colab("download", "-s", session, "/content/runs.tar.gz", str(local))
    with tarfile.open(local) as archive:
        archive.extractall(root, filter="data")
    logger.info("Results extracted into %s", root / "runs")


def watch(session: str, root: Path, interval: int = 120, fetch_results: bool = True) -> str:
    """Poll until the job ends; fetch each newly finished condition; fail fast if VM is lost."""
    fetched: set[str] = set()
    while True:
        state = remote_state(session, root)
        new = set(state["finished"]) - fetched
        if fetch_results and new:
            logger.info("Fetching newly finished conditions: %s", sorted(new))
            fetch(session, root)
            fetched |= new
        if state["status"].startswith(("DONE", "FAILED")):
            if fetch_results:
                fetch(session, root)
            logger.info("Job ended: %s", state["status"])
            return state["status"]
        logger.info("%s; finished: %s", state["status"] or "starting", state["finished"])
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["up", "sync", "train", "predict", "watch", "status", "fetch", "down"],
    )
    parser.add_argument("conditions", nargs="*", help=f"subset of {CONDITIONS} (train only)")
    parser.add_argument("--session", default="audit-train")
    parser.add_argument("--gpu", default="A100")
    parser.add_argument("--interval", type=int, default=120, help="watch polling seconds")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = Path(__file__).resolve().parents[3]
    try:
        if args.command == "up":
            up(args.session, args.gpu, root)
        elif args.command == "sync":
            sync(args.session, root)
        elif args.command == "train":
            unknown = set(args.conditions) - set(CONDITIONS)
            if unknown:
                parser.error(f"Unknown conditions: {sorted(unknown)}")
            train(args.session, root, args.conditions or list(CONDITIONS))
        elif args.command == "predict":
            predict(args.session)
        elif args.command == "watch":
            watch(args.session, root, args.interval)
        elif args.command == "status":
            status(args.session)
        elif args.command == "fetch":
            fetch(args.session, root)
        else:
            colab("stop", "-s", args.session)
    except VMLost as error:
        logger.error("%s: rerun `up` and `train`; finished conditions are resumed", error)
        raise SystemExit(3) from error
