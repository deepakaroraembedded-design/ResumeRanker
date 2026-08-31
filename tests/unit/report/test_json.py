from __future__ import annotations

import json
from pathlib import Path

import pytest

from resume_ranker.models.run import RunResult
from resume_ranker.report.json import ScorecardJsonWriter


@pytest.fixture
def json_dir(tmp_path: Path, sample_run: RunResult) -> Path:
    writer = ScorecardJsonWriter()
    result = writer.write(sample_run, tmp_path)
    assert result.ok
    return result.value


def test_json_files_written(json_dir: Path, sample_run: RunResult) -> None:
    for card in sample_run.scorecards:
        path = json_dir / f"{card.candidate_id}.scorecard.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["candidate_id"] == card.candidate_id
        assert data["composite"] == card.composite


def test_json_round_trip(json_dir: Path) -> None:
    path = json_dir / "c_abc123.scorecard.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["sub_scores"]["S1"]["value"] == 88.4
    assert data["matched"][0]["criterion"] == "python"
    assert data["gaps"][0]["criterion"] == "dbt"


def test_json_atomic_write(tmp_path: Path, sample_run: RunResult) -> None:
    writer = ScorecardJsonWriter()
    writer.write(sample_run, tmp_path)
    assert not list(tmp_path.rglob("*.tmp"))
