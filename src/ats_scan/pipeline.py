from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ats_scan.embeddings import create_embedding_client
from ats_scan.extract import load_extractors
from ats_scan.fairness import BlindRedactor
from ats_scan.fairness.impact import compute_adverse_impact_report
from ats_scan.integrity import HiddenTextDetector, InjectionDetector, KeywordStuffingDetector
from ats_scan.jobspec import JobSpecCompiler
from ats_scan.llm import create_llm_adapter
from ats_scan.models.common import Diagnostic, IntegrityFinding, StageResult
from ats_scan.models.config import FairnessConfig, IntegrityConfig, RootConfig
from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import RunContext, RunManifest, RunResult, ScoringContext
from ats_scan.models.scoring import (
    GapDetail,
    MatchDetail,
    Provenance,
    ScoreCard,
    SubScore,
)
from ats_scan.models.source import ExtractedText, SourceDocument
from ats_scan.ontology import from_config as ontology_from_config
from ats_scan.protocols import (
    EmbeddingClient,
    IntegrityDetector,
    LLMClient,
    OntologyIndex,
    Redactor,
    ReportWriter,
    Structurer,
    TextExtractor,
    TitleTaxonomy,
)
from ats_scan.report import (
    AuditJsonlWriter,
    CsvWriter,
    DiagnosticsCsvWriter,
    HtmlReportWriter,
    RunManifestJsonWriter,
    ScorecardJsonWriter,
    XlsxWriter,
    copy_selected_resumes,
)
from ats_scan.scoring import load_dimensions
from ats_scan.scoring.aggregate import aggregate
from ats_scan.scoring.confidence import confidence
from ats_scan.scoring.filters import evaluate_knockouts
from ats_scan.scoring.selection import select
from ats_scan.scoring.tiebreak import rank
from ats_scan.structure import HeuristicStructurer, HybridStructurer

ScoreFn = Callable[[CanonicalResume, JobSpec, ScoringContext], ScoreCard]
ScoreFnWithFindings = Callable[
    [CanonicalResume, JobSpec, ScoringContext, tuple[IntegrityFinding, ...]], ScoreCard
]


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

    def _candidate_id(self, doc: SourceDocument, resume: CanonicalResume) -> str:
        """Return a stable candidate id for *doc*.

        The structurer may not have access to the source document, so it often
        falls back to ``c_unknown``. When that happens, derive the id from the
        content hash (FR-104) or, as a fallback, from the resolved file path.
        """
        if resume.candidate_id and resume.candidate_id != "c_unknown":
            return resume.candidate_id
        if doc.content_sha256:
            return f"c_{doc.content_sha256[:8]}"
        path_hash = hashlib.sha256(str(Path(doc.path).resolve()).encode("utf-8")).hexdigest()
        return f"c_{path_hash[:8]}"

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
    ) -> tuple[tuple[IntegrityFinding, ...], tuple[Diagnostic, ...], tuple[str, ...]]:
        """Run all integrity detectors and return findings, diagnostics and flag codes."""
        findings: list[IntegrityFinding] = []
        diagnostics: list[Diagnostic] = []
        flags: list[str] = []
        for detector in self.integrity_detectors:
            for finding in detector.inspect(doc, text, resume):
                findings.append(finding)
                diagnostics.append(
                    Diagnostic(
                        stage="S2",
                        code=finding.code,
                        message=finding.message,
                    )
                )
                flags.append(finding.code)
        return tuple(findings), tuple(diagnostics), tuple(flags)

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
            resume = structure_result.value.model_copy(
                update={"candidate_id": self._candidate_id(doc, structure_result.value)}
            )

            findings, integrity_diagnostics, _flags = self._inspect_integrity(doc, text, resume)
            all_diagnostics.extend(integrity_diagnostics)

            redacted_resume, _reident_map = self.redactor.redact(resume)
            scorecard = self._score_with_findings(redacted_resume, jobspec, scoring_ctx, findings)
            scorecard = scorecard.model_copy(
                update={
                    "candidate_id": resume.candidate_id,
                    "job_id": jobspec.job_id,
                    "run_id": settings.run_id,
                }
            )
            scorecards.append(scorecard)
            resumes[resume.candidate_id] = resume

        ranked = rank(scorecards)
        ranked = select(ranked, settings.config.selection)
        ranked = self._add_explanations_and_provenance(ranked, settings, scoring_ctx)

        manifest_flags: list[str] = []
        selected_count = sum(1 for card in ranked if card.selected)
        selected_share = selected_count / max(len(ranked), 1)
        if selected_share > settings.config.selection.warn_if_selected_share_above:
            manifest_flags.append("HIGH_SELECTION_SHARE")
        ineligible_count = sum(1 for card in ranked if not card.eligible)
        knockout_share = ineligible_count / max(len(ranked), 1)
        if knockout_share > settings.config.selection.warn_if_knockout_excludes_share_above:
            manifest_flags.append("HIGH_KNOCKOUT_SHARE")

        manifest = RunManifest(
            run_id=settings.run_id,
            config_hash=settings.config_hash,
            ontology_version=self.ontology.version,
            code_version=settings.code_version,
            started_at=started_at,
            finished_at=_now_iso(),
            documents_in=len(documents),
            documents_failed=failed,
            model_identifiers={
                "embedding": settings.config.embeddings.model or "all-MiniLM-L6-v2",
                "llm": settings.config.llm.model,
                "ontology": self.ontology.version,
            },
            calibration_anchors={
                "anchor_low": scoring_ctx.pool.anchor_low,
                "anchor_high": scoring_ctx.pool.anchor_high,
                "p10": scoring_ctx.pool.p10,
                "p90": scoring_ctx.pool.p90,
            },
            flags=tuple(manifest_flags),
        )

        result = RunResult(
            manifest=manifest,
            scorecards=ranked,
            jobspec=jobspec,
            resumes=resumes,
            diagnostics=tuple(all_diagnostics),
        )

        if settings.output_dir:
            self._write_reports(result, settings.output_dir)

        return result

    def _score_with_findings(
        self,
        resume: CanonicalResume,
        spec: JobSpec,
        ctx: ScoringContext,
        findings: tuple[IntegrityFinding, ...],
    ) -> ScoreCard:
        """Invoke ``self.score_fn``, passing findings only if it accepts them."""
        score_fn: Any = self.score_fn
        sig = inspect.signature(score_fn)
        if "findings" in sig.parameters:
            return cast(ScoreCard, score_fn(resume, spec, ctx, findings=findings))
        return cast(ScoreCard, score_fn(resume, spec, ctx))

    def _add_explanations_and_provenance(
        self,
        cards: tuple[ScoreCard, ...],
        settings: RunSettings,
        scoring_ctx: ScoringContext,
    ) -> tuple[ScoreCard, ...]:
        """Attach recruiter-facing explanations and provenance to each scorecard."""
        provenance = Provenance(
            config_sha256=settings.config_hash,
            ontology_version=self.ontology.version,
            code_version=settings.code_version,
            models={
                "embedding": settings.config.embeddings.model or "all-MiniLM-L6-v2",
                "llm": settings.config.llm.model,
                "ontology": self.ontology.version,
            },
            scored_at=_now_iso(),
        )
        return tuple(
            card.model_copy(
                update={
                    "explanation": self.explain(card),
                    "provenance": provenance,
                }
            )
            for card in cards
        )

    def _write_reports(self, result: RunResult, out_dir: Path) -> None:
        """Write all registered report artefacts to *out_dir*.

        A failed artefact does not block the others; diagnostics are attached to
        the result. Artefacts are written atomically by each ReportWriter.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        for writer in self.report_writers:
            writer.write(result, out_dir)
        copy_selected_resumes(result, out_dir)

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
        """Produce an audit report from a completed run.

        Validates the manifest, returns counts by band and selection status, and,
        when a candidate_id -> group mapping is supplied, computes an adverse-impact
        report per TRD §11.3.
        """
        manifest = result.manifest
        by_band: dict[str, int] = {}
        for card in result.scorecards:
            by_band[card.band or "unknown"] = by_band.get(card.band or "unknown", 0) + 1

        report: dict[str, Any] = {
            "run_id": manifest.run_id,
            "valid": manifest.finished_at is not None,
            "documents_in": manifest.documents_in,
            "documents_failed": manifest.documents_failed,
            "scorecards": len(result.scorecards),
            "selected": sum(1 for c in result.scorecards if c.selected),
            "by_band": by_band,
            "demographics_groups": list(demographics.keys()) if demographics else [],
        }

        if demographics and "mapping" in demographics:
            mapping = demographics["mapping"]
            impact = compute_adverse_impact_report(
                result.scorecards,
                mapping,
            )
            report["adverse_impact"] = impact.model_dump(mode="json")

        return report

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


def build_pipeline(config: RootConfig, mode: str) -> Pipeline:
    """Wire a fully integrated Pipeline from the real component implementations.

    This is the integrator hook (C-15) called by the CLI for every command that
    needs the real engine. It imports the configured extractors, structurer,
    JobSpec compiler, ontology/title taxonomy, embedding client, LLM client,
    redactor, integrity detectors, report writers, and the scoring dimension
    registry, then returns a ready-to-run Pipeline.
    """
    ontology, titles = ontology_from_config(config.ontology)
    extractors = load_extractors()

    # Build the LLM adapter once. In hybrid mode it is used by the structurer and
    # by S3's LLM rubric; in offline mode it is left as None so dimensions degrade.
    llm: LLMClient | None = None
    if mode == "hybrid":
        placeholder_ctx = RunContext(run_id="pipeline-build", cache_dir=Path(".ats-cache"))
        llm = create_llm_adapter(placeholder_ctx, config.llm)

    structurer: Structurer = HeuristicStructurer()
    if mode == "hybrid" and llm is not None:
        structurer = HybridStructurer(llm=llm)

    jobspec_compiler = JobSpecCompiler()
    redactor = BlindRedactor(blind=config.fairness.blind)
    integrity_detectors = cast(
        list[IntegrityDetector],
        [
            HiddenTextDetector(config=config.integrity),
            KeywordStuffingDetector(config=config.integrity),
            InjectionDetector(),
        ],
    )

    embeddings: EmbeddingClient | None = None
    if config.embeddings.local:
        embeddings = create_embedding_client(config.embeddings)

    report_writers = _build_report_writers(config)
    dimensions = load_dimensions()
    score_fn = _build_score_fn(
        dimensions=dimensions,
        scoring_cfg=config.scoring,
        integrity_cfg=config.integrity,
        selection_cfg=config.selection,
        fairness_cfg=config.fairness,
        mode=mode,
    )

    return Pipeline(
        extractors=extractors,
        structurer=structurer,
        jobspec_compiler=jobspec_compiler,
        ontology=ontology,
        titles=titles,
        redactor=redactor,
        integrity_detectors=integrity_detectors,
        report_writers=report_writers,
        score_fn=score_fn,
        embeddings=embeddings,
        llm=llm,
    )


def _build_report_writers(config: RootConfig) -> list[ReportWriter]:
    """Return the report writers enabled by the output configuration."""
    formats = set(config.output.formats)
    writers: list[ReportWriter] = []
    if "csv" in formats:
        writers.append(CsvWriter())
    if "xlsx" in formats:
        writers.append(XlsxWriter())
    if "json" in formats:
        writers.append(ScorecardJsonWriter())
    if "html" in formats:
        writers.append(HtmlReportWriter())
    writers.append(AuditJsonlWriter())
    writers.append(DiagnosticsCsvWriter())
    writers.append(RunManifestJsonWriter())
    return writers


def _build_score_fn(
    dimensions: Mapping[str, object],
    scoring_cfg: object,
    integrity_cfg: object,
    selection_cfg: object,
    fairness_cfg: object,
    mode: str,
) -> Callable[..., ScoreCard]:
    """Return a closure that scores one resume against a JobSpec.

    The closure runs all registered dimensions, evaluates knockouts, aggregates
    sub-scores, computes confidence, and assembles a ScoreCard. It is the
    integration point for C-10..C-13.
    """
    from ats_scan.models.config import (
        ScoringConfig,
    )
    from ats_scan.protocols import Dimension

    typed_dimensions: Mapping[str, Dimension] = dimensions  # type: ignore[assignment]
    scoring_config: ScoringConfig = scoring_cfg  # type: ignore[assignment]
    integrity_config: IntegrityConfig = integrity_cfg  # type: ignore[assignment]
    fairness_config: FairnessConfig = fairness_cfg  # type: ignore[assignment]

    def _score(
        resume: CanonicalResume,
        spec: JobSpec,
        ctx: ScoringContext,
        findings: tuple[IntegrityFinding, ...] = (),
    ) -> ScoreCard:
        sub_scores: dict[str, SubScore] = {}
        for dim in typed_dimensions.values():
            sub = dim.score(resume, spec, ctx)
            sub_scores[sub.dimension] = sub

        matched: list[MatchDetail] = []
        gaps: list[GapDetail] = []
        for sub in sub_scores.values():
            detail = sub.detail or {}
            matches = detail.get("matches")
            if isinstance(matches, Sequence):
                matched.extend(matches)
            gap_items = detail.get("gaps")
            if isinstance(gap_items, Sequence):
                gaps.extend(gap_items)

        eligible, knockout_results = evaluate_knockouts(
            resume,
            spec,
            fairness_config,
            evaluators={},
        )

        aggregation = aggregate(
            sub_scores,
            scoring_config.weights,
            findings,
            scoring_config,
            integrity_config,
        )

        rubric_stdev: float | None = None
        s3 = sub_scores.get("S3")
        if s3 is not None and s3.detail:
            stdev = s3.detail.get("rubric_stdev")
            if isinstance(stdev, (int, float)):
                rubric_stdev = float(stdev)
        conf = confidence(resume, sub_scores, mode, rubric_stdev=rubric_stdev)

        flags: list[str] = list(aggregation.flags)
        reason_codes: list[str] = list(aggregation.reason_codes)
        for ko in knockout_results:
            if ko.verdict == "FAIL":
                flags.append("KNOCKOUT")
                reason_codes.append(ko.id)
            elif ko.verdict == "UNVERIFIED":
                flags.append("KO_UNVERIFIED")
                reason_codes.append(ko.id)
        if conf < 0.6:
            flags.append("LOW_CONFIDENCE")

        return ScoreCard(
            candidate_id=resume.candidate_id,
            job_id=spec.job_id,
            run_id="",
            eligible=eligible,
            knockout_results=knockout_results,
            sub_scores=sub_scores,
            base_score=aggregation.base_score,
            integrity_penalty=aggregation.integrity_penalty,
            composite=aggregation.composite,
            band=aggregation.band,
            confidence=conf,
            matched=tuple(matched),
            gaps=tuple(gaps),
            flags=tuple(flags),
            reason_codes=tuple(reason_codes),
        )

    return _score
