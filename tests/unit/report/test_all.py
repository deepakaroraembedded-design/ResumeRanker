from __future__ import annotations

from pathlib import Path

import pytest

from resume_ranker.models.common import StageResult
from resume_ranker.models.run import RunResult
from resume_ranker.report import write_all_reports


def test_write_all_reports_writes_all_artefacts(tmp_path: Path, sample_run: RunResult) -> None:
    results = write_all_reports(sample_run, tmp_path)
    assert results["scores.csv"].ok
    assert results["scores.xlsx"].ok
    assert results["candidates/*.scorecard.json"].ok
    assert results["report.html"].ok
    assert results["audit.jsonl"].ok
    assert results["diagnostics/*.csv"].ok
    assert results["selected"].ok

    assert (tmp_path / "scores.csv").exists()
    assert (tmp_path / "scores.xlsx").exists()
    assert (tmp_path / "candidates" / "c_abc123.scorecard.json").exists()
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "audit.jsonl").exists()
    assert (tmp_path / "diagnostics" / "errors.csv").exists()


def test_write_all_reports_isolates_failures(
    tmp_path: Path, sample_run: RunResult, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed writer must not prevent the other artefacts from being written."""

    class FailingCsvWriter:
        artefact = "scores.csv"

        def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]:
            raise RuntimeError("simulated CSV failure")

    monkeypatch.setattr("resume_ranker.report.CsvWriter", FailingCsvWriter)
    results = write_all_reports(sample_run, tmp_path)
    assert not results["scores.csv"].ok
    assert results["scores.xlsx"].ok
    assert results["report.html"].ok
