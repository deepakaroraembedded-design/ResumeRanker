from __future__ import annotations

import json
from pathlib import Path

import pytest

from ats_scan.models.run import RunResult
from ats_scan.report.audit import AuditJsonlWriter


@pytest.fixture
def audit_path(tmp_path: Path, sample_run: RunResult) -> Path:
    writer = AuditJsonlWriter()
    result = writer.write(sample_run, tmp_path)
    assert result.ok
    return result.value


def test_audit_one_line_per_candidate(audit_path: Path, sample_run: RunResult) -> None:
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(sample_run.scorecards)
    for line in lines:
        record = json.loads(line)
        assert record["run_id"] == "run_001"
        assert record["config_hash"] == "sha-config"
        assert record["ontology_version"] == "2026.07"
        assert record["code_version"] == "1.0.0"
        assert "decision_support_banner" in record


def test_audit_candidate_selection(audit_path: Path) -> None:
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(line) for line in lines]
    by_id = {r["candidate_id"]: r for r in records}
    assert by_id["c_abc123"]["selection_verdict"]["selected"] is True
    assert by_id["c_def456"]["selection_verdict"]["selected"] is False


def test_audit_sub_scores_and_evidence(audit_path: Path) -> None:
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    records = {json.loads(line)["candidate_id"]: json.loads(line) for line in lines}
    s1 = records["c_abc123"]["sub_scores"]["S1"]
    assert s1["value"] == 88.4
    assert s1["evidence"][0]["quote"] == "Python expert"


def test_audit_atomic_write(tmp_path: Path, sample_run: RunResult) -> None:
    writer = AuditJsonlWriter()
    writer.write(sample_run, tmp_path)
    assert not list(tmp_path.glob("*.tmp"))
