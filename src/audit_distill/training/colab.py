"""Drive training on a Colab GPU VM through the `colab` CLI (google-colab-cli).

`up` rents the VM and uploads a bundle (tracked files, `.git` for provenance, the
student data), then installs the locked environment with `uv sync --group train`.
`train` starts the conditions as a detached background job on the VM (a `colab exec`
call times out, training must not). `status` shows progress, `fetch` downloads the
results without per-epoch checkpoints, `down` releases the VM. Every step is explicit;
nothing here runs without the owner's approval of the GPU job.
"""

import argparse
import logging
import subprocess
import tarfile
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)
REMOTE = "/content/audit-distill"
CONDITIONS = ("label", "report", "report-vf")


def colab(*args: str, stdin: str | None = None) -> None:
    subprocess.run(["colab", *args], input=stdin, text=True, check=True)


def remote(session: str, code: str, timeout: int) -> None:
    """Run Python on the VM kernel; output streams to the local terminal."""
    colab("exec", "-s", session, "--timeout", str(timeout), stdin=code)


def shell(commands: list[str]) -> str:
    """Python source that runs shell commands in the repo on the VM and prints output."""
    lines = ["import subprocess"]
    for command in commands:
        lines.append(
            f"print(subprocess.run(['bash', '-lc', {command!r}], cwd={REMOTE!r}, "
            "capture_output=True, text=True).stdout[-4000:], flush=True)"
        )
    return "\n".join(lines)


def bundle(root: Path) -> Path:
    """Tracked files + `.git` + student data as one tarball (raw data never leaves)."""
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
    return path


def up(session: str, gpu: str, root: Path) -> None:
    colab("new", "-s", session, "--gpu", gpu)
    path = bundle(root)
    logger.info("Uploading %s (%.1f MB)", path.name, path.stat().st_size / 1e6)
    colab("upload", "-s", session, str(path), "/content/bundle.tar.gz")
    extract = (
        "import tarfile, os\n"
        f"os.makedirs({REMOTE!r}, exist_ok=True)\n"
        f"tarfile.open('/content/bundle.tar.gz').extractall({REMOTE!r})\n"
        "print('extracted')\n"
    )
    remote(session, extract, 120)
    setup = shell(
        [
            "pip install -q uv 2>&1 | tail -1; uv --version",
            "uv sync --locked --group train 2>&1 | tail -3",
            "nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv",
            "uv run python -c 'import torch; print(torch.__version__, "
            "torch.cuda.is_available(), torch.cuda.get_device_name(0))'",
            "git log --oneline -1; git status --short | head -5",
        ]
    )
    remote(session, setup, 1800)


def train(session: str, conditions: list[str]) -> None:
    runs = " ".join(conditions)
    job = (
        "set -u\ncd " + REMOTE + "\nmkdir -p runs\necho RUNNING > runs/STATUS\n"
        f"for c in {runs}; do\n"
        "  uv run python scripts/train.py --condition $c > runs/train-$c.log 2>&1 "
        "|| { echo FAILED $c > runs/STATUS; exit 1; }\n"
        "done\necho DONE > runs/STATUS\n"
    )
    code = (
        "import subprocess, pathlib\n"
        f"path = pathlib.Path({REMOTE!r}) / 'train_job.sh'\n"
        f"path.write_text({job!r})\n"
        "subprocess.Popen(['setsid', 'nohup', 'bash', str(path)], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)\n"
        "print('started', path)\n"
    )
    remote(session, code, 60)


def status(session: str) -> None:
    remote(
        session,
        shell(
            [
                "cat runs/STATUS 2>/dev/null || echo 'no job'",
                'for f in runs/train-*.log; do echo "== $f"; '
                "tail -c 1500 \"$f\" | tr '\\r' '\\n' | grep -v '^\\s*$' | tail -4; done",
                "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader",
            ]
        ),
        120,
    )


def fetch(session: str, root: Path) -> None:
    remote(
        session,
        shell(
            [
                "tar czf /content/runs.tar.gz --exclude=checkpoints runs",
                "ls -la /content/runs.tar.gz",
            ]
        ),
        600,
    )
    local = Path(tempfile.mkdtemp()) / "runs.tar.gz"
    colab("download", "-s", session, "/content/runs.tar.gz", str(local))
    with tarfile.open(local) as archive:
        archive.extractall(root, filter="data")
    logger.info("Results extracted into %s", root / "runs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["up", "train", "status", "fetch", "down"])
    parser.add_argument("conditions", nargs="*", help=f"subset of {CONDITIONS} (train only)")
    parser.add_argument("--session", default="audit-train")
    parser.add_argument("--gpu", default="H100")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = Path(__file__).resolve().parents[3]
    if args.command == "up":
        up(args.session, args.gpu, root)
    elif args.command == "train":
        unknown = set(args.conditions) - set(CONDITIONS)
        if unknown:
            parser.error(f"Unknown conditions: {sorted(unknown)}")
        train(args.session, args.conditions or list(CONDITIONS))
    elif args.command == "status":
        status(args.session)
    elif args.command == "fetch":
        fetch(args.session, root)
    else:
        colab("stop", "-s", args.session)
