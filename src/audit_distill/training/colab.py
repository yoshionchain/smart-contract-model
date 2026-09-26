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


class ExecHung(RuntimeError):
    """A `colab exec` call did not return in time; the VM may still be fine."""


def colab(*args: str, stdin: str | None = None) -> None:
    subprocess.run(["colab", *args], input=stdin, text=True, check=True)


def remote(session: str, code: str, timeout: int) -> str:
    """Run Python on the VM kernel and return its output (raises VMLost if it is gone)."""
    try:
        # `colab exec` can hang past its own timeout; enforce a hard local limit.
        result = subprocess.run(
            ["colab", "exec", "-s", session, "--timeout", str(timeout)],
            input=code,
            text=True,
            capture_output=True,
            timeout=timeout + 120,
        )
    except subprocess.TimeoutExpired as error:
        raise ExecHung(f"colab exec did not return within {timeout + 120} s") from error
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
        # Finished conditions and predictions of the current run, minus large weights,
        # which `sync` uploads in chunks (the VM's file API rejects large uploads).
        extra = [f for c in finished(root) for f in sorted(c.rglob("*")) if f.is_file()]
        extra += sorted(f for f in (root / run_dir(root) / "eval").rglob("*") if f.is_file())
        for file in extra:
            if file.stat().st_size <= CHUNK:
                archive.add(file, arcname=str(file.relative_to(root)))
    return path


CHUNK = 40_000_000


def upload_large(session: str, root: Path, file: Path) -> None:
    """Upload a file in chunks and reassemble it on the VM, checking its SHA-256."""
    import hashlib

    target = f"{REMOTE}/{file.relative_to(root)}"
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    parts = []
    with file.open("rb") as stream, tempfile.TemporaryDirectory() as temporary:
        for index, chunk in enumerate(iter(lambda: stream.read(CHUNK), b"")):
            part = Path(temporary) / f"part{index:03d}"
            part.write_bytes(chunk)
            remote_part = f"/content/upload/{file.name}.part{index:03d}"
            colab("upload", "-s", session, str(part), remote_part)
            parts.append(remote_part)
    code = (
        "import hashlib, pathlib\n"
        f"target = pathlib.Path({target!r}); target.parent.mkdir(parents=True, exist_ok=True)\n"
        f"data = b''.join(pathlib.Path(p).read_bytes() for p in {parts!r})\n"
        f"assert hashlib.sha256(data).hexdigest() == {digest!r}, 'checksum mismatch'\n"
        "target.write_bytes(data)\n"
        f"[pathlib.Path(p).unlink() for p in {parts!r}]\n"
        "print('assembled', target)\n"
    )
    print(remote(session, code, 300))


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
    for condition in finished(root):
        for file in sorted(condition.rglob("*")):
            if file.is_file() and file.stat().st_size > CHUNK:
                upload_large(session, root, file)
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


ADOPT = """
from colab_cli.common import state
from colab_cli.state import SessionState
from colab_cli.client import Variant
known = {{s.endpoint for s in state.store.list().values()}}
orphans = [a for a in state.client.list_assignments()
           if a.endpoint not in known and a.accelerator.value.lower() == {gpu!r}]
if len(orphans) != 1:
    raise SystemExit(f"expected one orphaned {gpu} assignment, found {{len(orphans)}}")
a = orphans[0]
state.store.add(SessionState(
    name={session!r}, token=a.runtime_proxy_info.token, url=a.runtime_proxy_info.url,
    endpoint=a.endpoint, token_expires_at=a.runtime_proxy_info.expires_at(),
    variant=Variant.GPU.value, accelerator=a.accelerator.value))
print("adopted", a.endpoint)
"""


def new_session(session: str, gpu: str) -> None:
    """`colab new`; if the CLI times out while Colab still assigns the GPU, adopt it."""
    try:
        colab("new", "-s", session, "--gpu", gpu)
        return
    except subprocess.CalledProcessError:
        logger.warning("`colab new` failed; looking for the GPU Colab assigned anyway")
    time.sleep(30)
    tools = subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True, check=True)
    python = Path(tools.stdout.strip()) / "google-colab-cli/bin/python"
    code = ADOPT.format(gpu=gpu.lower(), session=session)
    subprocess.run([str(python), "-c", code], check=True)


def up(session: str, gpu: str, root: Path) -> None:
    new_session(session, gpu)
    setup(session, root)


def setup(session: str, root: Path) -> None:
    """Upload the bundle and install the locked environment (background job)."""
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


def train(session: str, root: Path, conditions: list[str], seeds: list[int]) -> None:
    """Train each condition (for each extra seed); finished runs are skipped."""
    launch(session, "train", train_commands(root, conditions, seeds))


def train_commands(root: Path, conditions: list[str], seeds: list[int]) -> list[str]:
    base = run_dir(root)
    commands = []
    for seed in seeds or [None]:
        for c in conditions:
            name = c if seed is None else f"{c}-seed{seed}"
            flag = "" if seed is None else f" --seed {seed}"
            commands.append(
                f"[ -f {base}/{name}/selection.json ] || uv run python scripts/train.py "
                f"--condition {c}{flag} > runs/train-{name}.log 2>&1"
            )
    return commands


def predict_commands(seeds: list[int]) -> list[str]:
    """All modes of the main run, or with `seeds` only the SFT modes of those seeds."""
    if not seeds:
        return ["uv run python scripts/predict.py > runs/predict.log 2>&1"]
    return [
        f"uv run python scripts/predict.py --seed {s} > runs/predict-seed{s}.log 2>&1"
        for s in seeds
    ]


def predict(session: str, seeds: list[int]) -> None:
    launch(session, "predict", predict_commands(seeds))


def followup(session: str, root: Path, seeds: list[int]) -> None:
    """One chained job: extra-seed training, their predictions, the faithfulness test."""
    commands = train_commands(root, list(CONDITIONS), seeds) + predict_commands(seeds)
    commands.append("uv run python scripts/faithfulness.py > runs/faithfulness.log 2>&1")
    launch(session, "followup", commands)


def faithfulness(session: str) -> None:
    launch(
        session,
        "faithfulness",
        ["uv run python scripts/faithfulness.py > runs/faithfulness.log 2>&1"],
    )


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
                    "for f in runs/train-*.log runs/predict*.log runs/faithfulness.log; do "
                    "[ -f $f ] || continue; "
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
        try:
            state = remote_state(session, root)
        except ExecHung as error:
            logger.warning("%s; retrying", error)
            time.sleep(interval)
            continue
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
        choices=[
            "up",
            "setup",
            "sync",
            "train",
            "predict",
            "faithfulness",
            "followup",
            "watch",
            "status",
            "fetch",
            "down",
        ],
    )
    parser.add_argument("conditions", nargs="*", help=f"subset of {CONDITIONS} (train only)")
    parser.add_argument("--session", default="audit-train")
    parser.add_argument("--gpu", default="A100")
    parser.add_argument("--interval", type=int, default=120, help="watch polling seconds")
    parser.add_argument("--seeds", type=int, nargs="*", default=[], help="extra seeds")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = Path(__file__).resolve().parents[3]
    try:
        if args.command == "up":
            up(args.session, args.gpu, root)
        elif args.command == "setup":
            setup(args.session, root)
        elif args.command == "sync":
            sync(args.session, root)
        elif args.command == "train":
            unknown = set(args.conditions) - set(CONDITIONS)
            if unknown:
                parser.error(f"Unknown conditions: {sorted(unknown)}")
            train(args.session, root, args.conditions or list(CONDITIONS), args.seeds)
        elif args.command == "predict":
            predict(args.session, args.seeds)
        elif args.command == "faithfulness":
            faithfulness(args.session)
        elif args.command == "followup":
            followup(args.session, root, args.seeds)
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
