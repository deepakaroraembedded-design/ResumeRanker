from __future__ import annotations

from pydantic import BaseModel, Field


class RequiredSkill(BaseModel):
    """A required skill in a JobSpec with weight and optional knockout."""

    canonical: str
    weight: int = Field(..., ge=1, le=5)
    knockout: bool = False


class PreferredSkill(BaseModel):
    """A preferred skill in a JobSpec."""

    canonical: str
    weight: int = Field(..., ge=1, le=5)


class KnockoutRule(BaseModel):
    """A binary eligibility rule in a JobSpec."""

    id: str
    rule: str
    evidence_required: bool = True


class ResponsibilityChunk(BaseModel):
    """A weighted responsibility chunk for semantic similarity."""

    id: str
    text: str
    weight: int = Field(..., ge=1, le=5)


class ExperienceRequirement(BaseModel):
    """Experience requirements."""

    min_years: int = Field(..., ge=0)
    target_years: int = Field(..., ge=0)
    count_internships: bool = False


class EducationRequirement(BaseModel):
    """Education requirements."""

    min_level: str
    fields: tuple[str, ...] = ()
    equivalent_experience_allowed: bool = True
    knockout: bool = False


class DomainRequirement(BaseModel):
    """Domain/industry requirement."""

    industry: str
    naics: str | None = None
    required: bool = False


class JobSpec(BaseModel):
    """The compiled machine-readable form of a job description."""

    schema_version: str = "1.0"
    job_id: str
    title: str
    title_family: str | None = None
    target_seniority: str | None = None
    domain: DomainRequirement | None = None
    experience: ExperienceRequirement | None = None
    education: EducationRequirement | None = None
    required_skills: tuple[RequiredSkill, ...] = ()
    preferred_skills: tuple[PreferredSkill, ...] = ()
    certifications: tuple[dict[str, object], ...] = ()
    knockouts: tuple[KnockoutRule, ...] = ()
    responsibility_chunks: tuple[ResponsibilityChunk, ...] = ()
    compiled_by: str | None = None
    reviewed_by: str | None = None
    review_state: str | None = None
    warnings: tuple[str, ...] = ()
