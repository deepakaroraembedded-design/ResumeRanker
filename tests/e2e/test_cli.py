from __future__ import annotations

from pathlib import Path

import pytest
from tests.fakes import (
    FakeIntegrityDetector,
    FakeJobSpecCompiler,
    FakeOntology,
    FakeRedactor,
    FakeReportWriter,
    FakeStructurer,
    FakeTextExtractor,
    FakeTitleTaxonomy,
)
from typer.testing import CliRunner

from ats_scan.cli.main import app
from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.scoring import ScoreCard
from ats_scan.pipeline import Pipeline

runner = CliRunner()

pytestmark = pytest.mark.e2e


def _fake_scorecard(resume: CanonicalResume, spec: JobSpec, ctx: object) -> ScoreCard:
    return ScoreCard(
        candidate_id=resume.candidate_id,
        job_id=spec.job_id,
        run_id="run_e2e",
        composite=80.0,
        confidence=0.85,
    )


@pytest.fixture
def fake_pipeline() -> Pipeline:
    return Pipeline(
        extractors={"fake": FakeTextExtractor()},
        structurer=FakeStructurer(),
        jobspec_compiler=FakeJobSpecCompiler(),
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        redactor=FakeRedactor(),
        integrity_detectors=[FakeIntegrityDetector()],
        report_writers=[FakeReportWriter()],
        score_fn=_fake_scorecard,
    )


@pytest.fixture
def resumes_dir(tmp_path: Path) -> Path:
    d = tmp_path / "resumes"
    d.mkdir()
    (d / "candidate1.pdf").write_bytes(b"resume 1")
    (d / "candidate2.txt").write_text("resume 2")
    return d


@pytest.fixture
def jd_file(tmp_path: Path) -> Path:
    path = tmp_path / "jd.md"
    path.write_text("Senior Data Engineer\nPython, SQL", encoding="utf-8")
    return path


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "ats.yaml"
    path.write_text("selection:\n  threshold: 60.0\n", encoding="utf-8")
    return path


def test_validate_config_command(config_file: Path) -> None:
    result = runner.invoke(app, ["validate-config", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "selection" in result.output


def test_validate_config_rejects_missing_file() -> None:
    result = runner.invoke(app, ["validate-config", "--config", "/nonexistent.yaml"])
    assert result.exit_code == 2


def test_compile_jd_command(
    jd_file: Path, tmp_path: Path, fake_pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ats_scan.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
    out = tmp_path / "jobspec.yaml"
    result = runner.invoke(app, ["compile-jd", "--jd", str(jd_file), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_run_command(
    resumes_dir: Path,
    jd_file: Path,
    tmp_path: Path,
    fake_pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ats_scan.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "run",
            "--resumes",
            str(resumes_dir),
            "--jd",
            str(jd_file),
            "--out",
            str(out),
            "--mode",
            "offline",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "fake.txt").exists()


def test_run_command_rejects_input_as_output(
    resumes_dir: Path,
    jd_file: Path,
    tmp_path: Path,
    fake_pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ats_scan.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
    result = runner.invoke(
        app,
        [
            "run",
            "--resumes",
            str(resumes_dir),
            "--jd",
            str(jd_file),
            "--out",
            str(resumes_dir),
            "--mode",
            "offline",
        ],
    )
    assert result.exit_code == 2


def test_parse_command(
    resumes_dir: Path,
    tmp_path: Path,
    fake_pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ats_scan.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
    out = tmp_path / "parsed"
    result = runner.invoke(
        app,
        [
            "parse",
            "--resumes",
            str(resumes_dir),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output


def test_explain_command(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates"
    candidates.mkdir()
    card = ScoreCard(
        candidate_id="c_abc",
        job_id="jd_001",
        run_id="run_e2e",
        composite=77.0,
        confidence=0.8,
    )
    (candidates / "c_abc.scorecard.json").write_text(card.model_dump_json(), encoding="utf-8")
    result = runner.invoke(app, ["explain", "--out", str(tmp_path), "--candidate", "c_abc"])
    assert result.exit_code == 0, result.output
    assert "77.0" in result.output


def test_audit_command(tmp_path: Path) -> None:
    from ats_scan.models.run import RunManifest

    manifest = RunManifest(
        run_id="run_e2e",
        config_hash="hash",
        ontology_version="2026.07",
        code_version="0.1.0",
        started_at="2026-08-29T00:00:00Z",
        finished_at="2026-08-29T00:01:00Z",
        documents_in=1,
        documents_failed=0,
    )
    (tmp_path / "run_manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    cli_result = runner.invoke(app, ["audit", "--out", str(tmp_path)])
    assert cli_result.exit_code == 0, cli_result.output
    assert "run_e2e" in cli_result.output


def test_calibrate_command(
    tmp_path: Path,
    fake_pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ats_scan.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
    out = tmp_path / "calibration.json"
    result = runner.invoke(app, ["calibrate", "--resumes", str(tmp_path), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
