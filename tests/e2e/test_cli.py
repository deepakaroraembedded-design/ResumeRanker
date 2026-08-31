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

from resume_ranker.cli.main import app
from resume_ranker.models.jobspec import JobSpec
from resume_ranker.models.resume import CanonicalResume
from resume_ranker.models.scoring import ScoreCard
from resume_ranker.pipeline import Pipeline

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
    path = tmp_path / "resume-ranker.yaml"
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
    monkeypatch.setattr("resume_ranker.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
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
    monkeypatch.setattr("resume_ranker.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
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
    monkeypatch.setattr("resume_ranker.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
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
    monkeypatch.setattr("resume_ranker.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
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
    from resume_ranker.models.run import RunManifest

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


def test_audit_command_with_scorecards_and_demographics(tmp_path: Path) -> None:
    """Audit loads per-candidate scorecards and computes adverse impact."""
    import csv

    from resume_ranker.models.run import RunManifest

    manifest = RunManifest(
        run_id="run_e2e",
        config_hash="hash",
        ontology_version="2026.07",
        code_version="0.1.0",
        started_at="2026-08-29T00:00:00Z",
        finished_at="2026-08-29T00:01:00Z",
        documents_in=2,
        documents_failed=0,
    )
    (tmp_path / "run_manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    candidates = tmp_path / "candidates"
    candidates.mkdir()
    for cid, group in [("c_alice", "A"), ("c_bob", "B")]:
        card = ScoreCard(
            candidate_id=cid,
            job_id="jd_001",
            run_id="run_e2e",
            composite=80.0 if group == "A" else 75.0,
            selected=group == "A",
            confidence=0.8,
        )
        (candidates / f"{cid}.scorecard.json").write_text(card.model_dump_json(), encoding="utf-8")
    demo = tmp_path / "demo.csv"
    with demo.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["candidate_id", "group"])
        writer.writeheader()
        writer.writerow({"candidate_id": "c_alice", "group": "A"})
        writer.writerow({"candidate_id": "c_bob", "group": "B"})

    cli_result = runner.invoke(app, ["audit", "--out", str(tmp_path), "--demographics", str(demo)])
    assert cli_result.exit_code == 0, cli_result.output
    assert "adverse_impact" in cli_result.output
    assert '"A"' in cli_result.output
    assert '"B"' in cli_result.output


def test_calibrate_command(
    tmp_path: Path,
    fake_pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("resume_ranker.cli.main.build_pipeline", lambda _cfg, _mode: fake_pipeline)
    out = tmp_path / "calibration.json"
    result = runner.invoke(app, ["calibrate", "--resumes", str(tmp_path), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_run_command_with_real_pipeline(tmp_path: Path) -> None:
    """Run the full CLI against the real, unmonkey-patched build_pipeline."""
    import json

    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "alice.txt").write_text(
        "Alice\nPython developer with 5 years experience.\n", encoding="utf-8"
    )
    (resumes_dir / "bob.txt").write_text(
        "Bob\nJava developer with 3 years experience.\n", encoding="utf-8"
    )
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Senior Software Engineer\nPython\n", encoding="utf-8")
    out = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "run",
            "--resumes",
            str(resumes_dir),
            "--jd",
            str(jd_path),
            "--out",
            str(out),
            "--mode",
            "offline",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "2 scorecard(s)" in result.output

    assert out.exists()
    assert (out / "scores.csv").exists()
    assert (out / "report.html").exists()
    assert (out / "scores.xlsx").exists()
    assert (out / "audit.jsonl").exists()
    assert (out / "candidates").is_dir()
    assert (out / "diagnostics").is_dir()
    assert (out / "selected").is_dir()

    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["documents_in"] == 2
    assert manifest["documents_failed"] == 0

    scorecards_dir = out / "candidates"
    scorecard_files = list(scorecards_dir.glob("*.scorecard.json"))
    assert len(scorecard_files) == 2
    for card_path in scorecard_files:
        card = ScoreCard.model_validate_json(card_path.read_text(encoding="utf-8"))
        assert card.composite is not None
        assert card.band is not None
        assert card.rank is not None


def test_run_command_rejects_existing_output_directory_without_force(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "r1.txt").write_text("Alice Python 5 years", encoding="utf-8")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Senior Software Engineer\nPython\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    (out / "existing.txt").write_text("do not overwrite", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "run",
            "--resumes",
            str(resumes_dir),
            "--jd",
            str(jd_path),
            "--out",
            str(out),
            "--mode",
            "offline",
        ],
    )
    assert result.exit_code == 7, result.output


def test_run_command_rejects_hybrid_mode_without_provider(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "r1.txt").write_text("Alice Python 5 years", encoding="utf-8")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Senior Software Engineer\nPython\n", encoding="utf-8")
    out = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "run",
            "--resumes",
            str(resumes_dir),
            "--jd",
            str(jd_path),
            "--out",
            str(out),
            "--mode",
            "hybrid",
        ],
    )
    assert result.exit_code == 6, result.output
    assert "llm.provider" in result.output


def test_run_command_review_jobspec_flag(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Senior Software Engineer\nPython\n", encoding="utf-8")
    out = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "run",
            "--resumes",
            str(resumes_dir),
            "--jd",
            str(jd_path),
            "--out",
            str(out),
            "--mode",
            "offline",
            "--review-jobspec",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "review" in result.output.lower()


def test_run_command_dry_run(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "r1.txt").write_text("Alice Python 5 years", encoding="utf-8")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Senior Software Engineer\nPython\n", encoding="utf-8")
    out = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "run",
            "--resumes",
            str(resumes_dir),
            "--jd",
            str(jd_path),
            "--out",
            str(out),
            "--mode",
            "offline",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Would score 1 document" in result.output


def test_run_command_no_readable_resumes(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Senior Software Engineer\nPython\n", encoding="utf-8")
    out = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "run",
            "--resumes",
            str(resumes_dir),
            "--jd",
            str(jd_path),
            "--out",
            str(out),
            "--mode",
            "offline",
        ],
    )
    assert result.exit_code == 3, result.output


def test_parse_command_no_readable_resumes(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    out = tmp_path / "out"

    result = runner.invoke(
        app,
        ["parse", "--resumes", str(resumes_dir), "--out", str(out)],
    )
    assert result.exit_code == 3, result.output


def test_compile_jd_command_real_failure(tmp_path: Path) -> None:
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("", encoding="utf-8")
    out = tmp_path / "jobspec.yaml"

    result = runner.invoke(app, ["compile-jd", "--jd", str(jd_path), "--out", str(out)])
    assert result.exit_code == 4, result.output


def test_explain_command_scorecard_not_found(tmp_path: Path) -> None:
    result = runner.invoke(app, ["explain", "--out", str(tmp_path), "--candidate", "c_missing"])
    assert result.exit_code == 2, result.output


def test_explain_command_invalid_scorecard(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates"
    candidates.mkdir()
    (candidates / "c_bad.scorecard.json").write_text("not json", encoding="utf-8")
    result = runner.invoke(app, ["explain", "--out", str(tmp_path), "--candidate", "c_bad"])
    assert result.exit_code == 2, result.output


def test_validate_config_command_rejects_invalid_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text("{invalid", encoding="utf-8")
    result = runner.invoke(app, ["validate-config", "--config", str(config_path)])
    assert result.exit_code == 2, result.output


def test_audit_command_manifest_not_found(tmp_path: Path) -> None:
    result = runner.invoke(app, ["audit", "--out", str(tmp_path)])
    assert result.exit_code == 2, result.output


def test_audit_command_incomplete_manifest(tmp_path: Path) -> None:
    (tmp_path / "run_manifest.json").write_text('{"run_id": "x"}', encoding="utf-8")
    result = runner.invoke(app, ["audit", "--out", str(tmp_path)])
    assert result.exit_code == 2, result.output
