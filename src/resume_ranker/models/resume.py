from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass

from resume_ranker.models.source import ExtractionMetadata, SourceDocument


class DatePrecision(StrEnum):
    """How precisely a date was resolved."""

    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    PRESENT = "present"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    """Employment type for an experience entry."""

    FULL_TIME = "full_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


@dataclass(frozen=True)
class DateValue:
    """A resolved date with precision."""

    value: str | None
    precision: DatePrecision = DatePrecision.UNKNOWN


@dataclass(frozen=True)
class Location:
    """A geographic location."""

    city: str | None = None
    region: str | None = None
    country: str | None = None
    remote: bool | None = None


@dataclass(frozen=True)
class Identity:
    """Contact and identity information.

    All fields are None in blind mode.
    """

    full_name: str | None = None
    emails: tuple[str, ...] = ()
    phones: tuple[str, ...] = ()
    links: dict[str, str | None] = Field(default_factory=dict)
    location: Location | None = None


@dataclass(frozen=True)
class Bullet:
    """A single bullet of experience narrative."""

    text: str
    span: tuple[int, int] | None = None


class ExperienceEntry(BaseModel):
    """One work or project experience entry."""

    employer: str | None = None
    employer_normalised: str | None = None
    title_raw: str | None = None
    title_canonical: str | None = None
    title_family: str | None = None
    seniority: str | None = None
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    location: Location | None = None
    start: DateValue | None = None
    end: DateValue | None = None
    months: int | None = None
    bullets: tuple[Bullet, ...] = ()
    skills_evidenced: tuple[str, ...] = ()
    span: tuple[int, int] | None = None


class EducationEntry(BaseModel):
    """One education entry."""

    institution: str | None = None
    degree_level: str | None = None
    field: str | None = None
    start: DateValue | None = None
    end: DateValue | None = None
    span: tuple[int, int] | None = None


class Certification(BaseModel):
    """One certification or credential."""

    name: str
    canonical: str | None = None
    issuer: str | None = None
    issued: str | None = None
    expires: str | None = None
    status: str | None = None
    credential_id: str | None = None
    span: tuple[int, int] | None = None


@dataclass(frozen=True)
class EvidenceSpan:
    """A character span with optional page context."""

    span: tuple[int, int]
    quote: str
    page: int | None = None


class SkillMention(BaseModel):
    """A skill mention extracted from the resume."""

    raw: str
    canonical: str | None = None
    match_route: str | None = None
    sections: tuple[str, ...] = ()
    mentions: int = 0
    first_used: str | None = None
    last_used: str | None = None
    evidence_spans: tuple[tuple[int, int], ...] = ()


class ProjectEntry(BaseModel):
    """A project entry, same shape as experience without an employer."""

    title: str | None = None
    title_canonical: str | None = None
    title_family: str | None = None
    seniority: str | None = None
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    location: Location | None = None
    start: DateValue | None = None
    end: DateValue | None = None
    months: int | None = None
    bullets: tuple[Bullet, ...] = ()
    skills_evidenced: tuple[str, ...] = ()
    span: tuple[int, int] | None = None


class Timeline(BaseModel):
    """Calendar-union coverage summary."""

    total_months_covered: int | None = None
    gaps: tuple[dict[str, object], ...] = ()
    median_tenure_months: int | None = None
    role_count: int = 0


class IntegritySummary(BaseModel):
    """Integrity-related summary extracted from the resume."""

    flags: tuple[str, ...] = ()
    hidden_text_tokens: int = 0
    skills_token_share: float = 0.0
    injection_spans: tuple[tuple[int, int], ...] = ()


class CanonicalResume(BaseModel):
    """The canonical structured representation of a resume."""

    schema_version: str = "1.0"
    candidate_id: str
    source: SourceDocument | None = None
    extraction: ExtractionMetadata | None = None
    identity: Identity | None = None
    summary: dict[str, object | None] = Field(default_factory=dict)
    experience: tuple[ExperienceEntry, ...] = ()
    education: tuple[EducationEntry, ...] = ()
    certifications: tuple[Certification, ...] = ()
    skills: tuple[SkillMention, ...] = ()
    projects: tuple[ProjectEntry, ...] = ()
    timeline: Timeline | None = None
    integrity: IntegritySummary | None = None
    parse_completeness: float | None = Field(None, ge=0.0, le=1.0)
    diagnostics: tuple[dict[str, object], ...] = ()
