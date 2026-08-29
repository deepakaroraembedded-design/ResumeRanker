from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ats_scan.models.common import Diagnostic, StageResult
from ats_scan.models.config import RootConfig
from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import RunContext, RunManifest, RunResult, ScoringContext
from ats_scan.models.scoring import ScoreCard
from ats_scan.models.source import ExtractedText, SourceDocument
from ats_scan.protocols import (
    EmbeddingClient,
    IntegrityDetector,
    JobSpecCompiler,
    LLMClient,
    OntologyIndex,
    Redactor,
    ReportWriter,
    Structurer,
    TextExtractor,
    TitleTaxonomy,
)

ScoreFn = Callable[[CanonicalResume, JobSpec, ScoringContext], ScoreCard]


def _now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class RunSettings:
    """Extra execution metadata needed by the pipeline but not by the protocols."""

    run_id: str
    config: RootConfig
    config_hash: str
    code_version: str
    now: str
    output_dir: Path | None = None


class Pipeline:
    """Orchestrates the ATS-Scan stages end-to-end.

    The pipeline contains no scoring business logic. It wires together
    implementations of the frozen protocols and delegates the actual scoring
    decisions to a supplied ``score_fn`` (which is typically produced by the
    scoring/aggregation components). All stages are fault-isolated per document;
    a failure at any stage yields diagnostics and the run continues.
    """

    def __init__(
        self,
        *,
        extractors: Mapping[str, TextExtractor],
        structurer: Structurer,
        jobspec_compiler: JobSpecCompiler,
        ontology: OntologyIndex,
        titles: TitleTaxonomy,
        redactor: Redactor,
        integrity_detectors: Sequence[IntegrityDetector],
        report_writers: Sequence[ReportWriter],
        score_fn: ScoreFn,
        embeddings: EmbeddingClient | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        """Create a fully wired pipeline.

        Args:
            extractors: Registered text extractors by class name.
            structurer: Converts extracted text to a CanonicalResume.
            jobspec_compiler: Compiles a job-description source into a JobSpec.
            ontology: Skill ontology index.
            titles: Title taxonomy.
            redactor: Identity redactor for blind mode.
            integrity_detectors: Detectors to run on each document.
            report_writers: Writers for the output artefacts.
            score_fn: Callable that produces a ScoreCard from a resume, spec and
                scoring context. This is the integration point for C-10..C-13.
            embeddings: Optional embedding client for semantic scoring.
            llm: Optional LLM client for hybrid mode.
        """
        self.extractors = extractors
        self.structurer = structurer
        self.jobspec_compiler = jobspec_compiler
        self.ontology = ontology
        self.titles = titles
        self.redactor = redactor
        self.integrity_detectors = integrity_detectors
        self.report_writers = report_writers
        self.score_fn = score_fn
        self.embeddings = embeddings
        self.llm = llm

    def _make_run_context(self, settings: RunSettings) -> RunContext:
        """Create a protocol-grade RunContext from pipeline settings."""
        return RunContext(
            run_id=settings.run_id,
            config=settings.config.ingest,
            output_dir=settings.output_dir,
        )

    def _pick_extractor(self, doc: SourceDocument) -> TextExtractor | None:
        """Return the first extractor that reports support for *doc*."""
        for extractor in self.extractors.values():
            if extractor.supports(doc):
                return extractor
        return None

    def _extract(self, doc: SourceDocument, ctx: RunContext) -> StageResult[ExtractedText]:
        """Extract text from *doc*, returning diagnostics on no match."""
        extractor = self._pick_extractor(doc)
        if extractor is None:
            return StageResult(
                value=None,
                diagnostics=(
                    Diagnostic(
                        stage="S2",
                        code="ING_UNSUPPORTED_TYPE",
                        message=f"no extractor registered for media type {doc.media_type}",
                    ),
                ),
            )
        return extractor.extract(doc, ctx)

    def _structure(self, text: ExtractedText, ctx: RunContext) -> StageResult[CanonicalResume]:
        """Structure extracted text into a CanonicalResume."""
        return self.structurer.structure(text, ctx)

    def _inspect_integrity(
        self,
        doc: SourceDocument,
        text: ExtractedText,
        resume: CanonicalResume | None,
    ) -> tuple[tuple[Diagnostic, ...], tuple[str, ...]]:
        """Run all integrity detectors and return diagnostics and flag codes."""
        diagnostics: list[Diagnostic] = []
        flags: list[str] = []
        for detector in self.integrity_detectors:
            for finding in detector.inspect(doc, text, resume):
                diagnostics.append(
                    Diagnostic(
                        stage="S2",
                        code=finding.code,
                        message=finding.message,
                    )
                )
                flags.append(finding.code)
        return tuple(diagnostics), tuple(flags)

    def _build_scoring_context(self, settings: RunSettings) -> ScoringContext:
        """Create a ScoringContext from the run settings and pipeline services."""
        return ScoringContext(
            ontology=self.ontology,
            titles=self.titles,
            embeddings=self.embeddings,
            llm=self.llm,
            config=settings.config.scoring,
            now=settings.now,
        )

    def compile_jd(self, source: str, ctx: RunContext) -> StageResult[JobSpec]:
        """Compile a free-text or YAML job description into a JobSpec."""
        return self.jobspec_compiler.compile(source, ctx)

    def parse(self, doc: SourceDocument, ctx: RunContext) -> StageResult[CanonicalResume]:
        """Extract and structure a single document without scoring."""
        extract_result = self._extract(doc, ctx)
        if not extract_result.ok or extract_result.value is None:
            return StageResult(
                value=None,
                diagnostics=extract_result.diagnostics,
            )
        return self._structure(extract_result.value, ctx)

    def run(
        self,
        documents: Sequence[SourceDocument],
        jd_source: str,
        settings: RunSettings,
    ) -> RunResult:
        """Run the full pipeline over *documents* against *jd_source*.

        The pipeline compiles the job description, then streams through the
        documents one at a time: extract, structure, integrity inspect, redact,
        score. The full corpus is never held in memory; only the ScoreCards are
        collected. Reports are written by the registered report writers.
        """
        started_at = _now_iso()
        ctx = self._make_run_context(settings)
        jd_result = self.compile_jd(jd_source, ctx)
        if not jd_result.ok or jd_result.value is None:
            return RunResult(
                manifest=RunManifest(
                    run_id=settings.run_id,
                    config_hash=settings.config_hash,
                    ontology_version=self.ontology.version,
                    code_version=settings.code_version,
                    started_at=started_at,
                    finished_at=_now_iso(),
                    documents_in=len(documents),
                    documents_failed=len(documents),
                    flags=("JOBSPEC_COMPILE_FAILED",),
                ),
                jobspec=None,
                diagnostics=jd_result.diagnostics,
            )

        jobspec = jd_result.value
        scoring_ctx = self._build_scoring_context(settings)
        scorecards: list[ScoreCard] = []
        resumes: dict[str, CanonicalResume] = {}
        all_diagnostics: list[Diagnostic] = []
        failed = 0

        for doc in documents:
            extract_result = self._extract(doc, ctx)
            if not extract_result.ok or extract_result.value is None:
                failed += 1
                all_diagnostics.extend(extract_result.diagnostics)
                continue
            text = extract_result.value

            structure_result = self._structure(text, ctx)
            if not structure_result.ok or structure_result.value is None:
                failed += 1
                all_diagnostics.extend(structure_result.diagnostics)
                continue
            resume = structure_result.value

            integrity_diagnostics, _flags = self._inspect_integrity(doc, text, resume)
            all_diagnostics.extend(integrity_diagnostics)

            redacted_resume, _reident_map = self.redactor.redact(resume)
            scorecard = self.score_fn(redacted_resume, jobspec, scoring_ctx)
            scorecard = scorecard.model_copy(
                update={
                    "candidate_id": resume.candidate_id,
                    "job_id": jobspec.job_id,
                    "run_id": settings.run_id,
                }
            )
            scorecards.append(scorecard)
            resumes[resume.candidate_id] = resume

        manifest = RunManifest(
            run_id=settings.run_id,
            config_hash=settings.config_hash,
            ontology_version=self.ontology.version,
            code_version=settings.code_version,
            started_at=started_at,
            finished_at=_now_iso(),
            documents_in=len(documents),
            documents_failed=failed,
        )

        result = RunResult(
            manifest=manifest,
            scorecards=tuple(scorecards),
            jobspec=jobspec,
            resumes=resumes,
            diagnostics=tuple(all_diagnostics),
        )

        if settings.output_dir:
            self._write_reports(result, settings.output_dir)

        return result

    def _write_reports(self, result: RunResult, out_dir: Path) -> None:
        """Write all registered report artefacts to *out_dir*.

        A failed artefact does not block the others; diagnostics are attached to
        the result. Artefacts are written atomically by each ReportWriter.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        for writer in self.report_writers:
            writer.write(result, out_dir)

    def explain(self, scorecard: ScoreCard) -> str:
        """Return a concise human-readable explanation of a ScoreCard.

        TRD §6.1 — G-EXPL produces a recruiter-facing summary of at most 120
        words. In this wiring implementation the explanation is templated from
        the scorecard fields; a real LLM-based explanation would be supplied by
        the ``llm`` service and called here.
        """
        composite = scorecard.composite
        band = scorecard.band or "unknown"
        matched = ", ".join(m.criterion for m in scorecard.matched[:3])
        gaps = ", ".join(g.criterion for g in scorecard.gaps[:3])
        flags = ", ".join(scorecard.flags)
        text = (
            f"Composite {composite:.1f} ({band}). "
            f"Strongest matches: {matched or 'none'}. "
            f"Key gaps: {gaps or 'none'}. "
            f"Flags: {flags or 'none'}."
        )
        words = text.split()
        if len(words) > 120:
            text = " ".join(words[:120]) + "..."
        return text

    def audit(self, result: RunResult, demographics: Mapping[str, Any] | None) -> dict[str, Any]:
        """Produce a lightweight audit report from a completed run.

        A full adverse-impact report requires the fairness component; this wiring
        validates the manifest and returns counts by band and selection status.
        """
        manifest = result.manifest
        by_band: dict[str, int] = {}
        for card in result.scorecards:
            by_band[card.band or "unknown"] = by_band.get(card.band or "unknown", 0) + 1
        return {
            "run_id": manifest.run_id,
            "valid": manifest.finished_at is not None,
            "documents_in": manifest.documents_in,
            "documents_failed": manifest.documents_failed,
            "scorecards": len(result.scorecards),
            "selected": sum(1 for c in result.scorecards if c.selected),
            "by_band": by_band,
            "demographics_groups": list(demographics.keys()) if demographics else [],
        }

    def calibrate(
        self,
        labelled_set: Sequence[tuple[SourceDocument, float]],
        ctx: RunContext,
    ) -> dict[str, Any]:
        """Return a calibration report placeholder.

        The real weight-tuning procedure of TRD §5.7 is implemented by the
        scoring components; C-15 only wires the command and emits a report.
        """
        return {
            "run_id": ctx.run_id,
            "labelled_documents": len(labelled_set),
            "status": "not_implemented_in_isolated_component",
        }


def _null_pipeline() -> Pipeline:
    """Return a Pipeline whose dependencies are never accessed.

    Used by stateless helpers (explain, audit) that only call methods which do
    not read the wired dependencies. Runtime type checking is satisfied because
    the protocols are runtime_checkable and the methods ignore the attributes.
    """
    placeholder: Any = object()
    return Pipeline(
        extractors={},
        structurer=placeholder,
        jobspec_compiler=placeholder,
        ontology=placeholder,
        titles=placeholder,
        redactor=placeholder,
        integrity_detectors=[],
        report_writers=[],
        score_fn=placeholder,
    )


def explain_scorecard(scorecard: ScoreCard) -> str:
    """Return a concise explanation of *scorecard* without full pipeline state."""
    return _null_pipeline().explain(scorecard)


def audit_run(result: RunResult, demographics: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a lightweight audit report for *result* without full pipeline state."""
    return _null_pipeline().audit(result, demographics)


def build_pipeline(config: RootConfig, mode: str) -> Pipeline:  # noqa: ARG001
    """Wire a Pipeline from the real component implementations.

    In the integrated build this function imports the configured extractors,
    structurer, JobSpec compiler, ontology, embedding client, LLM client,
    redactor, integrity detectors, report writers, and the scoring dimension
    registry. In the C-15 isolated branch the real components are stubs, so this
    wiring function raises a clear runtime error indicating that integration must
    happen in the integrator branch.
    """
    raise NotImplementedError(
        "build_pipeline requires the real component implementations. "
        "Wire it in the integrator branch once C-01..C-14 are merged."
    )
