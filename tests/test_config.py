from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from audit_distill.data.settings import DataConfig, load_data_config


def test_config_resolves_paths() -> None:
    config = load_data_config(Path("configs/project.yaml"))
    assert config.datasets["dappscan"].path == Path("data/raw/dappscan").resolve()
    assert config.output_dir == Path("data/processed/reentrancy-v2.1").resolve()
    assert config.taxonomy_path == Path("configs/taxonomy.yaml").resolve()
    assert config.active_checks == ["REENTRANCY"]


def test_locked_token_budgets_and_unknown_fields() -> None:
    data = load_data_config(Path("configs/project.yaml")).model_dump()
    for key in ["max_code_tokens", "max_sequence_tokens", "max_report_tokens"]:
        changed = data | {"tokenizer": data["tokenizer"] | {key: 1}}
        with pytest.raises(ValidationError):
            DataConfig.model_validate(changed)
    with pytest.raises(ValidationError):
        DataConfig.model_validate(data | {"negative_sampling": "balance_classes"})


def test_training_and_data_budgets_agree_with_revision() -> None:
    config = load_data_config(Path("configs/project.yaml"))
    training = yaml.safe_load(Path("configs/training.yaml").read_text())
    assert config.spec_version == "2.1"
    assert training["max_seq_length"] == config.tokenizer.max_sequence_tokens == 8192
    assert training["model_revision"] == config.tokenizer.revision
    assert training["base_model"] == config.tokenizer.model_id
    assert training["gradient_accumulation_steps"] == 4
