from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from pydantic import BaseModel, Field

from resume_ranker.models.common import Diagnostic, StageResult
from resume_ranker.models.resume import (
    Bullet,
    CanonicalResume,
    Certification,
    DateValue,
    EducationEntry,
    EmploymentType,
    ExperienceEntry,
    Identity,
    Location,
    SkillMention,
)
from resume_ranker.models.run import RunContext
from resume_ranker.models.source import ExtractedText
from resume_ranker.protocols import LLMClient, Structurer
from resume_ranker.structure.dates import parse_date_range
from resume_ranker.structure.entities import (
    _month_from_iso,
    _now_from_iso,
    build_timeline,
    compute_parse_completeness,
    detect_multi_resume,
    structure_from_sections,
)
from resume_ranker.structure.sections import segment_sections


class _LLMExperienceEntry(BaseModel):
    """Internal LLM schema for one experience entry with evidence spans."""

    employer: str | None = None
    employer_span: tuple[int, int] | None = None
    title: str | None = None
    title_span: tuple[int, int] | None = None
    location: str | None = None
    location_span: tuple[int, int] | None = None
    employment_type: str | None = None
    start_date: str | None = None
    start_date_span: tuple[int, int] | None = None
    end_date: str | None = None
    end_date_span: tuple[int, int] | None = None
    bullets: list[str] = Field(default_factory=list)
    bullets_span: tuple[int, int] | None = None


class _LLMEducationEntry(BaseModel):
    """Internal LLM schema for one education entry with evidence spans."""

    institution: str | None = None
    institution_span: tuple[int, int] | None = None
    degree_level: str | None = None
    degree_level_span: tuple[int, int] | None = None
    field: str | None = None
    field_span: tuple[int, int] | None = None
    graduation_date: str | None = None
    graduation_date_span: tuple[int, int] | None = None


class _LLMCertification(BaseModel):
    """Internal LLM schema for one certification with evidence spans."""

    name: str | None = None
    name_span: tuple[int, int] | None = None
    issuer: str | None = None
    issuer_span: tuple[int, int] | None = None
    issued: str | None = None
    issued_span: tuple[int, int] | None = None
    expires: str | None = None
    expires_span: tuple[int, int] | None = None
    credential_id: str | None = None


class _LLMResumeOutput(BaseModel):
    """Internal LLM schema for a structured resume.

    Every field carries an optional evidence span. After parsing, the structurer
    verifies that the quoted span matches the source text; any mismatch causes
    the field to be treated as absent (FR-306).
    """

    full_name: str | None = None
    full_name_span: tuple[int, int] | None = None
    email: str | None = None
    email_span: tuple[int, int] | None = None
    phone: str | None = None
    phone_span: tuple[int, int] | None = None
    summary: str | None = None
    summary_span: tuple[int, int] | None = None
    experience: list[_LLMExperienceEntry] = Field(default_factory=list)
    education: list[_LLMEducationEntry] = Field(default_factory=list)
    certifications: list[_LLMCertification] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skills_span: tuple[int, int] | None = None


class _LLMResponse(BaseModel):
    """Wrapper so the LLM can return a single resume object."""

    resume: _LLMResumeOutput


class HybridStructurer(Structurer):
    """Hybrid structurer: LLM first, deterministic heuristic fallback.

    Implements the Structurer protocol (TRD §3.3 FR-305, FR-307). When an LLM
    client is supplied, it calls a schema-constrained parser and validates the
    response; on failure it falls back to the heuristic parser and records
    LLM_DEGRADED. In offline mode (llm=None) it uses the heuristic parser directly.
    """

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm
        self._heuristic = HeuristicStructurer()

    def structure(self, text: ExtractedText, ctx: RunContext) -> StageResult[CanonicalResume]:
        if self._llm is None:
            return self._heuristic.structure(text, ctx)

        try:
            result = asyncio.run(self._call_llm(text, ctx, self._llm))
        except Exception as exc:  # pragma: no cover - defensive guard
            result = StageResult(
                value=None,
                diagnostics=(
                    Diagnostic(
                        stage="S3",
                        code="LLM_DEGRADED",
                        message=f"LLM structuring failed: {exc}",
                    ),
                ),
            )

        if result.ok:
            return result

        # Fallback to heuristic and attach LLM_DEGRADED diagnostic.
        heuristic = self._heuristic.structure(text, ctx)
        diagnostics = tuple(result.diagnostics) + tuple(heuristic.diagnostics)
        if heuristic.value is None:
            return StageResult(value=None, diagnostics=diagnostics)
        return StageResult(
            value=heuristic.value.model_copy(
                update={
                    "diagnostics": tuple(asdict(d) for d in diagnostics),
                }
            ),
            diagnostics=diagnostics,
        )

    async def _call_llm(
        self, text: ExtractedText, ctx: RunContext, llm: LLMClient
    ) -> StageResult[CanonicalResume]:
        prompt = _PROMPT_TEMPLATE
        variables: dict[str, object] = {
            "text": text.text,
            "now": ctx.now or "",
        }
        result = await llm.structured(
            template=prompt,
            variables=variables,
            schema=_LLMResponse,
            trace="structure.hybrid",
        )
        if not result.ok or result.value is None:
            return StageResult(
                value=None,
                diagnostics=(
                    Diagnostic(
                        stage="S3",
                        code="LLM_DEGRADED",
                        message="LLM did not return a structured resume.",
                    ),
                ),
            )
        llm_output = result.value.samples[0]
        try:
            llm_resume = llm_output.resume
        except AttributeError:
            return StageResult(
                value=None,
                diagnostics=(
                    Diagnostic(
                        stage="S3",
                        code="LLM_DEGRADED",
                        message="LLM response schema mismatch.",
                    ),
                ),
            )
        resume = _llm_resume_to_canonical(text.text, llm_resume)
        # Validate against JSON schema by serialising and re-parsing.
        schema_path = Path("docs/contracts/canonical_resume.schema.json")
        if schema_path.exists():
            import jsonschema  # type: ignore[import-untyped]

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            try:
                jsonschema.validate(resume.model_dump(mode="json"), schema)
            except jsonschema.ValidationError as exc:
                return StageResult(
                    value=None,
                    diagnostics=(
                        Diagnostic(
                            stage="S3",
                            code="LLM_DEGRADED",
                            message=f"LLM resume failed schema validation: {exc}",
                        ),
                    ),
                )
        return StageResult(value=resume)


class HeuristicStructurer(Structurer):
    """Deterministic rule-based resume structurer.

    Implements the Structurer protocol without any external calls. It segments
    the text into sections, extracts entities, reconciles timelines, and never
    fabricates values.
    """

    def structure(self, text: ExtractedText, ctx: RunContext) -> StageResult[CanonicalResume]:
        now = _now_from_iso(ctx.now)
        sections = segment_sections(text.text, text.blocks)
        fields = structure_from_sections(text, sections, now)
        multi_resume = detect_multi_resume(sections)
        diagnostics: list[Diagnostic] = []
        if multi_resume:
            diagnostics.append(
                Diagnostic(
                    stage="S3",
                    code="MULTI_RESUME",
                    message="Multiple contact/identity blocks detected in one document.",
                )
            )
        resume = CanonicalResume(
            candidate_id="c_unknown",
            extraction=text.metadata,
            identity=fields.get("identity"),
            experience=fields.get("experience", ()),
            education=fields.get("education", ()),
            certifications=fields.get("certifications", ()),
            skills=fields.get("skills", ()),
            projects=fields.get("projects", ()),
            timeline=fields.get("timeline"),
            parse_completeness=None,
            diagnostics=tuple(asdict(d) for d in diagnostics),
        )
        completeness = compute_parse_completeness(resume)
        resume = resume.model_copy(update={"parse_completeness": completeness})
        return StageResult(
            value=resume,
            diagnostics=tuple(diagnostics),
        )


def _verify_span(text: str, span: tuple[int, int] | None, quote: str) -> bool:
    """Return True if *span* points to *quote* in *text*."""
    if span is None or len(span) != 2:
        return False
    start, end = span
    if not (0 <= start < end <= len(text)):
        return False
    return text[start:end] == quote


def _llm_resume_to_canonical(text: str, llm_resume: _LLMResumeOutput) -> CanonicalResume:
    """Convert an LLM schema response into a CanonicalResume, dropping unverified fields."""
    full_name = (
        llm_resume.full_name
        if _verify_span(text, llm_resume.full_name_span, llm_resume.full_name or "")
        else None
    )
    emails: tuple[str, ...] = (
        (llm_resume.email,)
        if llm_resume.email and _verify_span(text, llm_resume.email_span, llm_resume.email)
        else ()
    )
    phones: tuple[str, ...] = (
        (llm_resume.phone,)
        if llm_resume.phone and _verify_span(text, llm_resume.phone_span, llm_resume.phone)
        else ()
    )
    identity = Identity(full_name=full_name, emails=emails, phones=phones)

    summary: dict[str, object | None] = {}
    if _verify_span(text, llm_resume.summary_span, llm_resume.summary or ""):
        summary = {"summary": llm_resume.summary}

    experience: list[ExperienceEntry] = []
    for exp in llm_resume.experience:
        employer = (
            exp.employer if _verify_span(text, exp.employer_span, exp.employer or "") else None
        )
        title = exp.title if _verify_span(text, exp.title_span, exp.title or "") else None
        location = None
        if exp.location and _verify_span(text, exp.location_span, exp.location):
            location = Location(city=exp.location)
        start: DateValue | None = None
        end: DateValue | None = None
        if exp.start_date:
            range_pair = parse_date_range(exp.start_date)
            if range_pair:
                start, _ = range_pair
        if exp.end_date:
            range_pair = parse_date_range(exp.end_date)
            if range_pair:
                _, end = range_pair
        bullets: list[Bullet] = []
        if _verify_span(text, exp.bullets_span, "\n".join(exp.bullets)):
            for bullet in exp.bullets:
                bullets.append(Bullet(text=bullet))
        months = None
        if start and start.value and end and end.value:
            start_m = _month_from_iso(start.value)
            end_m = _month_from_iso(end.value)
            if start_m is not None and end_m is not None:
                months = end_m - start_m + 1
        employment_type = EmploymentType.FULL_TIME
        if exp.employment_type:
            try:
                employment_type = EmploymentType(exp.employment_type.lower())
            except ValueError:
                employment_type = EmploymentType.FULL_TIME
        experience.append(
            ExperienceEntry(
                employer=employer,
                title_raw=title,
                location=location,
                employment_type=employment_type,
                start=start,
                end=end,
                months=months,
                bullets=tuple(bullets),
            )
        )

    education: list[EducationEntry] = []
    for edu in llm_resume.education:
        institution = (
            edu.institution
            if _verify_span(text, edu.institution_span, edu.institution or "")
            else None
        )
        degree_level = (
            edu.degree_level
            if _verify_span(text, edu.degree_level_span, edu.degree_level or "")
            else None
        )
        field = edu.field if _verify_span(text, edu.field_span, edu.field or "") else None
        grad_date: DateValue | None = None
        if edu.graduation_date:
            range_pair = parse_date_range(edu.graduation_date)
            if range_pair:
                grad_date, _ = range_pair
        education.append(
            EducationEntry(
                institution=institution,
                degree_level=degree_level,
                field=field,
                end=grad_date,
            )
        )

    certifications: list[Certification] = []
    for cert in llm_resume.certifications:
        name = cert.name if _verify_span(text, cert.name_span, cert.name or "") else None
        issuer = cert.issuer if _verify_span(text, cert.issuer_span, cert.issuer or "") else None
        certifications.append(
            Certification(
                name=name or "",
                issuer=issuer,
                issued=cert.issued,
                expires=cert.expires,
                credential_id=cert.credential_id,
            )
        )

    skills: list[SkillMention] = []
    if _verify_span(text, llm_resume.skills_span, ", ".join(llm_resume.skills)):
        for skill in llm_resume.skills:
            skills.append(SkillMention(raw=skill))

    timeline = build_timeline(tuple(experience))
    resume = CanonicalResume(
        candidate_id="c_unknown",
        identity=identity,
        summary=summary,
        experience=tuple(experience),
        education=tuple(education),
        certifications=tuple(certifications),
        skills=tuple(skills),
        projects=(),
        timeline=timeline,
        parse_completeness=None,
    )
    return resume.model_copy(update={"parse_completeness": compute_parse_completeness(resume)})


_PROMPT_TEMPLATE: str = """\
You are a resume parser. Extract the resume below into the requested JSON schema.
Every field that you populate must include a character-offset span [start, end)
into the source text that exactly matches the value you provide. If a value is
not present, return null for the field and null for its span.

Run date (ISO-8601): {{now}}

Source text:
{{text}}
"""
