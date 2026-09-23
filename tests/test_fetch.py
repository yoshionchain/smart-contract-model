import subprocess
from pathlib import Path

import pytest

from audit_distill.config import Upstream
from audit_distill.data.fetch import fetch, verify_checkout


def test_pinned_fetch_and_dirty_checkout_refusal(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", str(origin)], check=True, capture_output=True)
    source = origin / "DAppSCAN-source/contracts/project/x.sol"
    source.parent.mkdir(parents=True)
    source.write_text("contract X {}")
    (origin / "README.md").write_text("Fixture")
    excluded = origin / "DAppSCAN-source/audit_report/excluded.txt"
    excluded.parent.mkdir(parents=True)
    excluded.write_text("Must not be fetched into the working tree")
    subprocess.run(["git", "-C", str(origin), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(origin),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    revision = subprocess.check_output(
        ["git", "-C", str(origin), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    upstream = Upstream(repository=str(origin), revision=revision, path=tmp_path / "checkout")
    fetch(upstream, dappscan=True)
    assert (upstream.path / source.relative_to(origin)).is_file()
    assert not (upstream.path / excluded.relative_to(origin)).exists()
    assert verify_checkout(upstream)["commit"] == revision
    fetch(upstream, dappscan=True)
    (upstream.path / "README.md").write_text("Edited locally")
    with pytest.raises(ValueError, match="dirty"):
        fetch(upstream, dappscan=True)
    with pytest.raises(ValueError, match="Revision mismatch"):
        verify_checkout(upstream.model_copy(update={"revision": "0" * 40}))
