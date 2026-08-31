from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar, Protocol, TypeVar, runtime_checkable

from resume_ranker.models.common import IntegrityFinding, StageResult
from resume_ranker.models.embeddings import Vector
from resume_ranker.models.jobspec import JobSpec
from resume_ranker.models.llm import LLMResult
from resume_ranker.models.ontology import SkillMatch, SkillRelation, TitleMatch
from resume_ranker.models.resume import CanonicalResume
from resume_ranker.models.run import RunContext, RunResult, ScoringContext
from resume_ranker.models.scoring import SubScore
from resume_ranker.models.source import ExtractedText, SourceDocument

T = TypeVar("T")


@runtime_checkable
class TextExtractor(Protocol):
    """Extracts text from a SourceDocument."""

    media_types: ClassVar[frozenset[str]]

    def supports(self, doc: SourceDocument) -> bool: ...
    def extract(self, doc: SourceDocument, ctx: RunContext) -> StageResult[ExtractedText]: ...


@runtime_checkable
class Structurer(Protocol):
    """Turns extracted text into a CanonicalResume."""

    def structure(self, text: ExtractedText, ctx: RunContext) -> StageResult[CanonicalResume]: ...


@runtime_checkable
class JobSpecCompiler(Protocol):
    """Compiles a free-text job description into a JobSpec."""

    def compile(self, source: str, ctx: RunContext) -> StageResult[JobSpec]: ...


@runtime_checkable
class OntologyIndex(Protocol):
    """Curated skill graph."""

    version: str

    def canonicalise(self, raw: str) -> SkillMatch | None: ...
    def relation(self, candidate: str, target: str) -> SkillRelation: ...
    def is_timeless(self, canonical: str) -> bool: ...


@runtime_checkable
class TitleTaxonomy(Protocol):
    """Normalised job-title taxonomy."""

    def normalise(self, raw_title: str) -> TitleMatch | None: ...
    def similarity(self, a: TitleMatch, b: TitleMatch) -> float: ...
    def seniority_gap(self, role: TitleMatch, target: TitleMatch) -> int: ...


@runtime_checkable
class Dimension(Protocol):
    """One of the ten scoring dimensions S1..S10."""

    id: ClassVar[str]
    name: ClassVar[str]
    requires: ClassVar[frozenset[str]]

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore: ...


@runtime_checkable
class LLMClient(Protocol):
    """Provider-agnostic LLM adapter."""

    async def structured(
        self,
        *,
        template: str,
        variables: Mapping[str, object],
        schema: type[T],
        samples: int = 1,
        trace: str,
    ) -> StageResult[LLMResult[T]]: ...


@runtime_checkable
class EmbeddingClient(Protocol):
    """Provider-agnostic embedding adapter."""

    dimensions: int

    async def embed(self, texts: Sequence[str]) -> Sequence[Vector]: ...


@runtime_checkable
class IntegrityDetector(Protocol):
    """Inspects a document for manipulation."""

    code: ClassVar[str]

    def inspect(
        self, doc: SourceDocument, text: ExtractedText, resume: CanonicalResume | None
    ) -> Sequence[IntegrityFinding]: ...


@runtime_checkable
class Redactor(Protocol):
    """Redacts identity attributes for blind mode."""

    def redact(self, resume: CanonicalResume) -> tuple[CanonicalResume, dict[str, str]]: ...


@runtime_checkable
class ReportWriter(Protocol):
    """Writes one output artefact."""

    artefact: ClassVar[str]

    def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]: ...
