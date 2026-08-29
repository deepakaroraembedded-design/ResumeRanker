from __future__ import annotations

from pathlib import Path

import pytest

from ats_scan.models.run import RunResult
from ats_scan.report.html import HtmlReportWriter


@pytest.fixture
def html_path(tmp_path: Path, sample_run: RunResult) -> Path:
    writer = HtmlReportWriter()
    result = writer.write(sample_run, tmp_path)
    assert result.ok
    return result.value


def test_html_is_self_contained(html_path: Path) -> None:
    text = html_path.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html>")
    assert "<style>" in text
    assert "http://" not in text
    assert "https://" not in text
    assert 'src="' not in text


def test_html_banner_and_review_queue(html_path: Path, sample_run: RunResult) -> None:
    text = html_path.read_text(encoding="utf-8")
    assert "This output is decision support only" in text
    assert "Review Queue" in text
    assert "c_def456" in text
    assert "LOW_CONFIDENCE" in text


def test_html_ranked_candidates(html_path: Path, sample_run: RunResult) -> None:
    text = html_path.read_text(encoding="utf-8")
    assert "Alice Smith" in text
    assert "c_abc123" in text
    assert "87.06" in text
    assert "Matched Requirements" in text
    assert "Python expert" in text
    assert "Missing Requirements" in text
    assert "dbt" in text


def test_html_blind_mode_degrades_to_candidate_id(blind_run: RunResult, tmp_path: Path) -> None:
    writer = HtmlReportWriter()
    result = writer.write(blind_run, tmp_path)
    assert result.ok
    text = result.value.read_text(encoding="utf-8")
    assert "c_abc123" in text
    assert "Alice Smith" not in text


def test_html_pool_context(html_path: Path) -> None:
    text = html_path.read_text(encoding="utf-8")
    assert "Pool Context" in text
    assert "Composite Histogram" in text
    assert "Band Counts" in text
    assert "Knockout Exclusions" in text
    assert "KO_WORK_AUTH" in text


def test_html_atomic_write(tmp_path: Path, sample_run: RunResult) -> None:
    writer = HtmlReportWriter()
    writer.write(sample_run, tmp_path)
    assert not list(tmp_path.glob("*.tmp"))
