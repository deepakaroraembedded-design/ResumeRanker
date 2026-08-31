from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from resume_ranker.config import ConfigResolver
from resume_ranker.errors import ConfigurationError


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "ats.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "scoring": {
                    "weights": {"S1": 25, "S2": 10},
                },
                "selection": {"threshold": 65.0},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_config_defaults_when_no_file() -> None:
    resolver = ConfigResolver()
    cfg, cfg_hash = resolver.resolve()
    assert cfg.scoring.weights["S1"] == 30
    assert cfg.selection.threshold == 70.0
    assert len(cfg_hash) == 64


def test_config_file_overrides_defaults(config_file: Path) -> None:
    resolver = ConfigResolver(config_file)
    cfg, _cfg_hash = resolver.resolve()
    assert cfg.scoring.weights["S1"] == 25
    assert cfg.scoring.weights["S2"] == 10
    assert cfg.selection.threshold == 65.0


def test_env_var_overrides_file(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATS_SCORING__WEIGHTS__S1", "20")
    resolver = ConfigResolver(config_file)
    cfg, _cfg_hash = resolver.resolve()
    assert cfg.scoring.weights["S1"] == 20


def test_cli_override_highest_precedence(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATS_SCORING__WEIGHTS__S1", "20")
    resolver = ConfigResolver(config_file)
    cfg, _cfg_hash = resolver.resolve({"scoring": {"weights": {"S1": 15}}})
    assert cfg.scoring.weights["S1"] == 15


def test_invalid_config_raises_configuration_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump({"scoring": {"weights": "not-a-dict"}}))
    resolver = ConfigResolver(path)
    with pytest.raises(ConfigurationError):
        resolver.resolve()


def test_config_hash_is_stable_and_redacts_secrets(tmp_path: Path) -> None:
    path = tmp_path / "ats.yaml"
    path.write_text(yaml.safe_dump({"llm": {"provider": "openai", "api_key": "secret"}}))
    resolver = ConfigResolver(path)
    cfg, cfg_hash = resolver.resolve()
    assert "secret" not in cfg_hash
    assert cfg.llm.provider == "openai"


def test_env_var_coerces_booleans_and_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATS_FAIRNESS__BLIND", "false")
    monkeypatch.setenv("ATS_LLM__CONCURRENCY", "8")
    resolver = ConfigResolver()
    cfg, _cfg_hash = resolver.resolve()
    assert cfg.fairness.blind is False
    assert cfg.llm.concurrency == 8


def teardown_module() -> None:
    for key in list(os.environ):
        if key.startswith("ATS_"):
            del os.environ[key]
