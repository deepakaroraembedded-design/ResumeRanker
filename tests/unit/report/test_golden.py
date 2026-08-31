from __future__ import annotations

from pathlib import Path

import pytest

from resume_ranker.models.run import RunResult
from resume_ranker.report.csv import CsvWriter

GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.mark.golden
def test_csv_golden_file(tmp_path: Path, sample_run: RunResult) -> None:
    """Compare CSV output to the checked-in golden file for a fixed RunResult."""
    writer = CsvWriter()
    result = writer.write(sample_run, tmp_path)
    assert result.ok
    generated = result.value.read_text(encoding="utf-8")
    expected = (GOLDEN_DIR / "scores.csv").read_text(encoding="utf-8")
    assert generated == expected
