from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from resume_ranker.models.common import IntegrityFinding, StageResult
from resume_ranker.models.embeddings import Vector
from resume_ranker.models.jobspec import JobSpec
from resume_ranker.models.llm import LLMResult
from resume_ranker.models.ontology import SkillMatch, SkillRelation, TitleMatch
from resume_ranker.models.resume import CanonicalResume, Identity, IntegritySummary
from resume_ranker.models.run import RunContext, RunResult, ScoringContext
from resume_ranker.models.scoring import SubScore
from resume_ranker.models.source import ExtractedText, ExtractionMetadata, SourceDocument, TextBlock
from resume_ranker.protocols import (
    Dimension,
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


class FakeTextExtractor(TextExtractor):
    """A fake extractor that returns the same text for every supported document."""

    media_types = frozenset(["application/pdf", "text/plain"])

    def supports(self, doc: SourceDocument) -> bool:
        return doc.media_type in self.media_types

    def extract(self, doc: SourceDocument, ctx: RunContext) -> StageResult[ExtractedText]:
        text = f"Extracted from {doc.path}"
        return StageResult(
            value=ExtractedText(
                text=text,
                metadata=ExtractionMetadata(method="fake"),
                blocks=(TextBlock(text=text, page=0, bbox=(0.0, 0.0, 1.0, 1.0)),),
            )
        )


class FakeStructurer(Structurer):
    """A fake structurer that returns a minimal CanonicalResume."""

    def structure(self, text: ExtractedText, ctx: RunContext) -> StageResult[CanonicalResume]:
        candidate_id = "c_fake001"
        return StageResult(
            value=CanonicalResume(
                candidate_id=candidate_id,
                identity=Identity(full_name="Candidate Fake"),
                integrity=IntegritySummary(),
                parse_completeness=1.0,
            )
        )


class FakeJobSpecCompiler(JobSpecCompiler):
    """A fake JobSpec compiler."""

    def compile(self, source: str, ctx: RunContext) -> StageResult[JobSpec]:
        return StageResult(
            value=JobSpec(
                job_id="jd_fake001",
                title=source.strip().splitlines()[0] if source.strip() else "Fake Job",
            )
        )


class FakeOntology(OntologyIndex):
    """A fake ontology with a small, deterministic skill graph."""

    version = "2026.07"

    _ALIASES: dict[str, str] = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
    }
    _TIMELESS: frozenset[str] = {"sql", "statistics", "linear algebra", "python"}

    def canonicalise(self, raw: str) -> SkillMatch | None:
        lower = raw.lower().strip()
        canonical = self._ALIASES.get(lower, lower)
        return SkillMatch(canonical=canonical, raw=raw, relation=SkillRelation.ALIAS)

    def relation(self, candidate: str, target: str) -> SkillRelation:
        c = candidate.lower().strip()
        t = target.lower().strip()
        if c == t:
            return SkillRelation.EXACT
        if c in self._ALIASES and self._ALIASES[c] == t:
            return SkillRelation.ALIAS
        return SkillRelation.NONE

    def is_timeless(self, canonical: str) -> bool:
        return canonical.lower() in self._TIMELESS


class FakeTitleTaxonomy(TitleTaxonomy):
    """A fake title taxonomy."""

    def normalise(self, raw_title: str) -> TitleMatch | None:
        lower = raw_title.lower().strip()
        return TitleMatch(family=lower, seniority="senior", raw=raw_title, normalised=lower)

    def similarity(self, a: TitleMatch, b: TitleMatch) -> float:
        if a.family == b.family:
            return 1.0
        return 0.15

    def seniority_gap(self, role: TitleMatch, target: TitleMatch) -> int:
        return 0


class FakeLLMClient(LLMClient):
    """Fake LLM client that replays canned JSON keyed by the call trace."""

    async def structured(
        self,
        *,
        template: str,
        variables: dict[str, object],
        schema: type[Any],
        samples: int = 1,
        trace: str,
    ) -> StageResult[LLMResult[Any]]:
        sample = schema.__name__ if hasattr(schema, "__name__") else {}
        return StageResult(value=LLMResult(samples=(sample,) * samples))


class FakeEmbeddingClient(EmbeddingClient):
    """Fake embedding client with deterministic hash-based vectors."""

    dimensions = 384

    def _vector(self, text: str) -> Vector:
        import hashlib

        seed = hashlib.sha256(text.encode()).digest()
        floats = []
        for i in range(self.dimensions):
            floats.append(((seed[i % len(seed)] + i) % 255) / 255.0 * 2.0 - 1.0)
        return tuple(floats)

    async def embed(self, texts: Sequence[str]) -> Sequence[Vector]:
        return [self._vector(t) for t in texts]


class FakeIntegrityDetector(IntegrityDetector):
    """Fake integrity detector that always returns no findings."""

    code = "FAKE_INTEGRITY"

    def inspect(
        self, doc: SourceDocument, text: ExtractedText, resume: CanonicalResume | None
    ) -> Sequence[IntegrityFinding]:
        return ()


class FakeRedactor(Redactor):
    """Fake redactor that returns the resume unchanged."""

    def redact(self, resume: CanonicalResume) -> tuple[CanonicalResume, dict[str, str]]:
        return resume, {}


class FakeReportWriter(ReportWriter):
    """Fake report writer that creates an empty file."""

    artefact = "fake.txt"

    def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]:
        path = out_dir / self.artefact
        path.write_text("fake report", encoding="utf-8")
        return StageResult(value=path)


class StubDimension(Dimension):
    """A dimension that always returns a fixed value."""

    id = "STUB"
    name = "Stub dimension"
    requires = frozenset()

    def __init__(self, value: float | None = 50.0) -> None:
        self._value = value

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        return SubScore(dimension=self.id, value=self._value, evidence=())
