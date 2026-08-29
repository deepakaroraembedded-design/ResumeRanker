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

from ats_scan.models.common import StageResult
from ats_scan.models.config import RootConfig
from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import RunContext
from ats_scan.models.scoring import Band, ScoreCard
from ats_scan.models.source import SourceDocument
from ats_scan.pipeline import Pipeline
from ats_scan.pipeline import RunSettings as PipelineRunSettings


def _make_scorecard(resume: CanonicalResume, spec: JobSpec, ctx: object) -> ScoreCard:
    return ScoreCard(
        candidate_id=resume.candidate_id,
        job_id=spec.job_id,
        run_id="run_test",
        composite=75.0,
        confidence=0.8,
    )


@pytest.fixture
def pipeline() -> Pipeline:
    return Pipeline(
        extractors={"fake": FakeTextExtractor()},
        structurer=FakeStructurer(),
        jobspec_compiler=FakeJobSpecCompiler(),
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        redactor=FakeRedactor(),
        integrity_detectors=[FakeIntegrityDetector()],
        report_writers=[FakeReportWriter()],
        score_fn=_make_scorecard,
    )


@pytest.fixture
def source_doc() -> SourceDocument:
    return SourceDocument(
        path="resume.pdf",
        content_sha256="abc123",
        bytes=1234,
        pages=2,
        mtime="2026-08-29T00:00:00Z",
        media_type="application/pdf",
    )


def test_parse_pipeline(pipeline: Pipeline, source_doc: SourceDocument) -> None:
    ctx = RunContext(run_id="run_test")
    result = pipeline.parse(source_doc, ctx)
    assert result.ok
    assert result.value is not None
    assert result.value.candidate_id == "c_fake001"


def test_run_pipeline_writes_reports(
    pipeline: Pipeline, source_doc: SourceDocument, tmp_path: Path
) -> None:
    settings = PipelineRunSettings(
        run_id="run_test",
        config=RootConfig(),
        config_hash="hash",
        code_version="0.1.0",
        now="2026-08-29",
        output_dir=tmp_path,
    )
    result = pipeline.run([source_doc], "Senior Data Engineer", settings)
    assert result.manifest.documents_in == 1
    assert result.manifest.documents_failed == 0
    assert len(result.scorecards) == 1
    assert (tmp_path / "fake.txt").exists()


def test_run_pipeline_reports_failure_on_unsupported_type(
    pipeline: Pipeline, tmp_path: Path
) -> None:
    doc = SourceDocument(
        path="image.png",
        content_sha256="def456",
        bytes=100,
        pages=None,
        mtime="2026-08-29T00:00:00Z",
        media_type="image/png",
    )
    settings = PipelineRunSettings(
        run_id="run_test",
        config=RootConfig(),
        config_hash="hash",
        code_version="0.1.0",
        now="2026-08-29",
        output_dir=tmp_path,
    )
    result = pipeline.run([doc], "Senior Data Engineer", settings)
    assert result.manifest.documents_failed == 1
    assert len(result.scorecards) == 0


def test_compile_jd(pipeline: Pipeline) -> None:
    ctx = RunContext(run_id="run_test")
    result = pipeline.compile_jd("Senior Data Engineer\nPython, SQL", ctx)
    assert result.ok
    assert result.value is not None
    assert result.value.job_id == "jd_fake001"


def test_explain_scorecard(pipeline: Pipeline) -> None:
    card = ScoreCard(
        candidate_id="c_abc123",
        job_id="jd_001",
        run_id="run_test",
        composite=82.5,
        confidence=0.9,
    )
    explanation = pipeline.explain(card)
    assert "82.5" in explanation
    assert len(explanation.split()) <= 120


def test_audit_run(pipeline: Pipeline) -> None:
    from ats_scan.models.run import RunManifest, RunResult

    result = RunResult(
        manifest=RunManifest(
            run_id="run_test",
            config_hash="hash",
            ontology_version="2026.07",
            code_version="0.1.0",
            started_at="2026-08-29T00:00:00Z",
            finished_at="2026-08-29T00:01:00Z",
            documents_in=2,
            documents_failed=0,
        ),
        scorecards=(
            ScoreCard(
                candidate_id="c1",
                job_id="jd",
                run_id="run",
                composite=80.0,
                confidence=0.85,
                band=Band.GOOD,
            ),
            ScoreCard(
                candidate_id="c2",
                job_id="jd",
                run_id="run",
                composite=90.0,
                confidence=0.9,
                band=Band.STRONG,
            ),
        ),
    )
    report = pipeline.audit(result, None)
    assert report["valid"] is True
    assert report["scorecards"] == 2
    assert report["by_band"]["good"] == 1
    assert report["by_band"]["strong"] == 1


def test_run_pipeline_fails_when_jd_compilation_fails(
    pipeline: Pipeline, source_doc: SourceDocument, tmp_path: Path
) -> None:
    class FailingCompiler(FakeJobSpecCompiler):
        def compile(self, source: str, ctx: RunContext) -> StageResult[JobSpec]:
            from ats_scan.models.common import Diagnostic, StageResult

            return StageResult(
                value=None, diagnostics=(Diagnostic(stage="S5", code="JD_FAIL", message="fail"),)
            )

    pipeline.jobspec_compiler = FailingCompiler()
    settings = PipelineRunSettings(
        run_id="run_test",
        config=RootConfig(),
        config_hash="hash",
        code_version="0.1.0",
        now="2026-08-29",
        output_dir=tmp_path,
    )
    result = pipeline.run([source_doc], "bad", settings)
    assert result.manifest.documents_failed == 1
    assert "JOBSPEC_COMPILE_FAILED" in result.manifest.flags
