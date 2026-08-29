from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic.dataclasses import dataclass


class Band(StrEnum):
    """Composite score band."""

    STRONG = "strong"
    GOOD = "good"
    BORDERLINE = "borderline"
    WEAK = "weak"
    NOT_A_MATCH = "not_a_match"


class MatchRoute(StrEnum):
    """How a skill was matched to the ontology."""

    EXACT = "exact"
    ALIAS = "alias"
    CASE = "case"
    FUZZY = "fuzzy"
    EMBEDDING = "embedding"
    CHILD = "child"
    PARENT = "parent"
    TRANSFERABLE = "transferable"
    NONE = "none"


@dataclass(frozen=True)
class Evidence:
    """Citation that supports a scoring claim.

    span: character offsets into the source text.
    quote: MUST equal text[span[0]:span[1]].
    page: optional source page number.
    source: which document the span indexes into.
    """

    span: tuple[int, int]
    quote: str
    page: int | None = None
    source: Literal["resume", "jobspec"] = "resume"


@dataclass(frozen=True)
class SubScore:
    """A single dimension score.

    value: None means the dimension was unavailable and its weight should be
        redistributed by the aggregation stage.
    """

    dimension: str
    value: float | None
    evidence: tuple[Evidence, ...] = ()
    detail: dict[str, Any] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @field_validator("value")
    @classmethod
    def _value_in_range(cls, value: float | None) -> float | None:
        if value is not None and not (0.0 <= value <= 100.0):
            raise ValueError(f"SubScore value must be in [0, 100], got {value}")
        return value


@dataclass(frozen=True)
class KnockoutResult:
    """The outcome of one knockout rule."""

    id: str
    verdict: Literal["PASS", "FAIL", "UNVERIFIED"]
    evidence: Evidence | None = None


@dataclass(frozen=True)
class MatchDetail:
    """A single matched requirement with its supporting evidence."""

    criterion: str
    weight: int
    match: float
    route: MatchRoute | None = None
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class GapDetail:
    """A single unmet requirement."""

    criterion: str
    weight: int
    match: float = 0.0
    searched: tuple[str, ...] = ()
    note: str = "no evidence found"


@dataclass(frozen=True)
class Provenance:
    """Provenance recorded in a ScoreCard."""

    config_sha256: str
    ontology_version: str
    code_version: str
    models: dict[str, str | None]
    scored_at: str


class ScoreCard(BaseModel):
    """The full per-candidate scoring output."""

    schema_version: str = "1.0"
    candidate_id: str
    job_id: str
    run_id: str
    eligible: bool = True
    knockout_results: tuple[KnockoutResult, ...] = ()
    sub_scores: dict[str, SubScore] = Field(default_factory=dict)
    base_score: float | None = None
    integrity_penalty: float = 0.0
    composite: float | None = None
    band: Band | None = None
    rank: int | None = None
    selected: bool = False
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    matched: tuple[MatchDetail, ...] = ()
    gaps: tuple[GapDetail, ...] = ()
    flags: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    explanation: str = ""
    provenance: Provenance | None = None


class PoolStatistics(BaseModel):
    """Calibration statistics used by S3."""

    p10: float | None = None
    p90: float | None = None
    anchor_low: float = 0.25
    anchor_high: float = 0.70
    size: int = 0
