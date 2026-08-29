from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ats_scan.models.common import Diagnostic
from ats_scan.models.config import IngestConfig, ScoringConfig
from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.scoring import PoolStatistics, ScoreCard


class RunContext(BaseModel):
    """Context available to every pipeline stage."""

    run_id: str
    config: IngestConfig | None = None
    now: str | None = None  # ISO-8601 date used by date-resolution stages
    output_dir: Path | None = None
    cache_dir: Path | None = None
    diagnostics: tuple[Diagnostic, ...] = ()


class ScoringContext(BaseModel):
    """Context available to every scoring dimension.

    This is deliberately narrow: dimensions reach shared services only through it.
    """

    ontology: object  # OntologyIndex protocol, resolved at runtime
    titles: object  # TitleTaxonomy protocol
    embeddings: object | None = None  # EmbeddingClient protocol
    llm: object | None = None  # LLMClient protocol
    config: ScoringConfig
    pool: PoolStatistics = Field(default_factory=PoolStatistics)
    now: str  # ISO-8601 date; recency scoring takes time from here


class RunManifest(BaseModel):
    """Provenance and counts written to the run manifest."""

    schema_version: str = "1.0"
    run_id: str
    config_hash: str
    ontology_version: str
    code_version: str
    model_identifiers: dict[str, str | None] = Field(default_factory=dict)
    started_at: str
    finished_at: str | None = None
    documents_in: int = 0
    documents_failed: int = 0
    cache_hits: int = 0
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    retries: int = 0
    timings: dict[str, float] = Field(default_factory=dict)
    calibration_anchors: dict[str, float | None] = Field(default_factory=dict)
    flags: tuple[str, ...] = ()


class RunResult(BaseModel):
    """The final output of a full run."""

    manifest: RunManifest
    scorecards: tuple[ScoreCard, ...] = ()
    jobspec: JobSpec | None = None
    resumes: dict[str, CanonicalResume] = Field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
