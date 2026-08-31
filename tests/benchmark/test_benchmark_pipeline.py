from __future__ import annotations

from collections.abc import Callable

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

from resume_ranker.models.config import RootConfig
from resume_ranker.models.resume import CanonicalResume
from resume_ranker.models.scoring import ScoreCard
from resume_ranker.models.source import SourceDocument
from resume_ranker.pipeline import Pipeline, RunSettings


def _make_scorecard(resume: CanonicalResume, spec: object, ctx: object) -> ScoreCard:
    return ScoreCard(
        candidate_id=resume.candidate_id,
        job_id="jd_bench",
        run_id="run_bench",
        composite=75.0,
        confidence=0.8,
    )


def _build_pipeline() -> Pipeline:
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


def test_pipeline_run_benchmark(benchmark: Callable[[Callable[[], None]], None]) -> None:
    """Benchmark the pipeline run orchestration over a small corpus."""
    pipeline = _build_pipeline()
    docs = [
        SourceDocument(
            path=f"resume_{i}.pdf",
            content_sha256=f"sha{i}",
            bytes=1024,
            pages=2,
            mtime="2026-08-29T00:00:00Z",
            media_type="application/pdf",
        )
        for i in range(50)
    ]
    settings = RunSettings(
        run_id="run_bench",
        config=RootConfig(),
        config_hash="hash",
        code_version="0.1.0",
        now="2026-08-29",
    )

    def run() -> None:
        pipeline.run(docs, "Senior Data Engineer", settings)

    benchmark(run)
