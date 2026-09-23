"""Shared fixtures: an empty v2.1 ledger over temporary source checkouts."""

from pathlib import Path

import pytest
import yaml

from audit_distill.data.ledger import Ledger
from audit_distill.data.settings import load_data_config


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    config = load_data_config(Path("configs/project.yaml"))
    sources = {
        name: source.model_copy(update={"path": tmp_path / name})
        for name, source in config.datasets.items()
    }
    for source in sources.values():
        source.path.mkdir()
        (source.path / "labels.json").write_text("{}")
    config = config.model_copy(update={"datasets": sources, "output_dir": tmp_path / "output"})
    return Ledger(config, yaml.safe_load(config.taxonomy_path.read_text()))
