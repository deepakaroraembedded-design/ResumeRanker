from __future__ import annotations

import csv
from pathlib import Path

import pytest

from resume_ranker.models.run import RunResult
from resume_ranker.report.diagnostics import DiagnosticsCsvWriter


@pytest.fixture
def diagnostics_dir(tmp_path: Path, sample_run: RunResult) -> Path:
    writer = DiagnosticsCsvWriter()
    result = writer.write(sample_run, tmp_path)
    assert result.ok
    return result.value


def test_errors_csv(diagnostics_dir: Path) -> None:
    path = diagnostics_dir / "errors.csv"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].startswith("# This output is decision support only")
    rows = list(csv.DictReader(lines[1:]))
    assert len(rows) == 1
    assert rows[0]["stage"] == "S2"
    assert rows[0]["code"] == "EXT_CORRUPT"


def test_knockout_stats_csv(diagnostics_dir: Path) -> None:
    path = diagnostics_dir / "knockout_stats.csv"
    text = path.read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()[1:]))
    assert any(r["rule_id"] == "KO_WORK_AUTH" and r["FAIL"] == "1" for r in rows)


def test_unmapped_skills_csv(diagnostics_dir: Path) -> None:
    path = diagnostics_dir / "unmapped_skills.csv"
    text = path.read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()[1:]))
    assert any(r["raw_skill"] == "MysterySkill" for r in rows)


def test_diagnostics_atomic_write(tmp_path: Path, sample_run: RunResult) -> None:
    writer = DiagnosticsCsvWriter()
    writer.write(sample_run, tmp_path)
    assert not list(tmp_path.rglob("*.tmp"))
