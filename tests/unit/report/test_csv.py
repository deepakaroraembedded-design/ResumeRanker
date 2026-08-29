from __future__ import annotations

import csv
from pathlib import Path

import pytest

from ats_scan.models.run import RunResult
from ats_scan.report.csv import CsvWriter

EXPECTED_COLUMNS = [
    "rank",
    "candidate_id",
    "file",
    "name",
    "composite",
    "band",
    "selected",
    "eligible",
    "confidence",
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    "S6",
    "S7",
    "S8",
    "S9",
    "S10",
    "matched_required",
    "missing_required",
    "relevant_years",
    "flags",
    "reason_codes",
    "explanation",
]


@pytest.fixture
def csv_path(tmp_path: Path, sample_run: RunResult) -> Path:
    writer = CsvWriter()
    result = writer.write(sample_run, tmp_path)
    assert result.ok
    return result.value


def test_csv_columns_and_banner(csv_path: Path) -> None:
    text = csv_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].startswith("# This output is decision support only")
    reader = csv.DictReader(lines[1:])
    assert reader.fieldnames == EXPECTED_COLUMNS


def test_csv_values(csv_path: Path) -> None:
    rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()[1:]))
    assert len(rows) == 2

    alice = rows[0]
    assert alice["candidate_id"] == "c_abc123"
    assert alice["name"] == "Alice Smith"
    assert alice["file"] == "resumes/abc123.pdf"
    assert alice["composite"] == "87.06"
    assert alice["band"] == "strong"
    assert alice["selected"] == "true"
    assert alice["eligible"] == "true"
    assert alice["confidence"] == "0.91"
    assert alice["S1"] == "88.40"
    assert alice["S4"] == "92.00"
    assert alice["matched_required"] == "python=1.00"
    assert alice["missing_required"] == "dbt(w=2)"
    assert alice["relevant_years"] == "7.20"
    assert alice["flags"] == ""
    assert alice["reason_codes"] == ""

    bob = rows[1]
    assert bob["candidate_id"] == "c_def456"
    assert bob["name"] == "Bob Jones"
    assert bob["composite"] == "42.50"
    assert bob["band"] == "weak"
    assert bob["selected"] == "false"
    assert bob["eligible"] == "false"
    assert bob["confidence"] == "0.55"
    assert bob["flags"] == "LOW_CONFIDENCE"
    assert bob["reason_codes"] == "KO_WORK_AUTH"


def test_csv_blind_name_is_empty(blind_run: RunResult, tmp_path: Path) -> None:
    writer = CsvWriter()
    result = writer.write(blind_run, tmp_path)
    assert result.ok
    rows = list(csv.DictReader(result.value.read_text(encoding="utf-8").splitlines()[1:]))
    assert rows[0]["name"] == ""


def test_csv_atomic_write(tmp_path: Path, sample_run: RunResult) -> None:
    writer = CsvWriter()
    writer.write(sample_run, tmp_path)
    assert not list(tmp_path.glob("*.tmp"))
