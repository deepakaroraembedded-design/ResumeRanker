from __future__ import annotations

from datetime import date

from ats_scan.models.resume import EmploymentType, ExperienceEntry
from ats_scan.models.source import ExtractedText, ExtractionMetadata
from ats_scan.structure.entities import (
    build_timeline,
    compute_parse_completeness,
    detect_multi_resume,
    extract_certifications,
    extract_education,
    extract_experience,
    extract_identity,
    extract_skills,
    structure_from_sections,
)
from ats_scan.structure.sections import Section, SectionType, segment_sections


class TestExtractIdentity:
    """Tests for contact/identity extraction."""

    def test_extracts_email_and_name(self) -> None:
        text = "Jane Doe\njane.doe@example.com\n+1 555 123 4567"
        section = Section(type=SectionType.CONTACT, heading=None, start=0, end=len(text), text=text)
        identity = extract_identity(text, section)
        assert identity.full_name == "Jane Doe"
        assert identity.emails == ("jane.doe@example.com",)
        assert identity.phones == ("+1 555 123 4567",)

    def test_no_fabrication(self) -> None:
        section = Section(
            type=SectionType.CONTACT,
            heading=None,
            start=0,
            end=4,
            text="Jane",
        )
        identity = extract_identity("Jane", section)
        assert identity.full_name == "Jane"
        assert identity.emails == ()
        assert identity.phones == ()


class TestExtractExperience:
    """Tests for experience entry extraction per TRD §3.3 FR-302."""

    def test_parses_role_header(self) -> None:
        text = "Acme Corp | Senior Software Engineer | 2020 – 2024\n- Built Python systems."
        section = Section(
            type=SectionType.EXPERIENCE,
            heading=None,
            start=0,
            end=len(text),
            text=text,
        )
        entries = extract_experience(section, date(2026, 8, 29))
        assert len(entries) == 1
        entry = entries[0]
        assert entry.employer == "Acme Corp"
        assert entry.title_raw == "Senior Software Engineer"
        assert entry.start is not None
        assert entry.start.value == "2020-01-01"
        assert entry.end is not None
        assert entry.end.value == "2024-01-01"
        assert entry.months == 49
        assert len(entry.bullets) == 1

    def test_present_end_uses_now(self) -> None:
        text = "Acme Corp | Engineer | 2020 – Present"
        section = Section(
            type=SectionType.EXPERIENCE,
            heading=None,
            start=0,
            end=len(text),
            text=text,
        )
        entries = extract_experience(section, date(2026, 8, 29))
        assert entries[0].end is not None
        assert entries[0].end.value == "2026-08-29"


class TestExtractEducation:
    """Tests for education entry extraction per TRD §3.3 FR-309."""

    def test_parses_bs_line(self) -> None:
        text = "BS in Computer Science, University of Example, 2016"
        section = Section(
            type=SectionType.EDUCATION,
            heading=None,
            start=0,
            end=len(text),
            text=text,
        )
        entries = extract_education(section)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.institution == "University of Example"
        assert entry.degree_level == "BS"
        assert entry.field == "Computer Science"
        assert entry.end is not None
        assert entry.end.value == "2016-01-01"


class TestExtractSkills:
    """Tests for skill harvesting per TRD §3.3 FR-308."""

    def test_harvests_from_all_sections(self) -> None:
        text = """\
Python, AWS

Experience
Built Python and AWS systems.

Education
Used Python in research.
"""
        sections = segment_sections(text)
        skills = extract_skills(text, sections)
        by_raw = {s.raw: s for s in skills}
        assert "Python" in by_raw
        python = by_raw["Python"]
        # Should appear in both contact/skills and experience/education sections.
        assert len(python.sections) >= 2
        assert python.mentions >= 2
        assert python.evidence_spans


class TestBuildTimeline:
    """Tests for calendar-union timeline per TRD §3.3 FR-304."""

    def test_overlapping_roles_not_double_counted(self) -> None:
        entries = (
            ExperienceEntry(
                employer="A",
                start=date_value("2020-01-01"),
                end=date_value("2024-12-01"),
                months=60,
            ),
            ExperienceEntry(
                employer="B",
                start=date_value("2022-01-01"),
                end=date_value("2025-12-01"),
                months=48,
            ),
        )
        timeline = build_timeline(entries)
        assert timeline.total_months_covered == 72  # 2020-01..2025-12

    def test_empty_timeline(self) -> None:
        timeline = build_timeline(())
        assert timeline.total_months_covered == 0
        assert timeline.role_count == 0
        assert timeline.median_tenure_months is None


class TestDetectMultiResume:
    """Tests for multi-resume detection per TRD §12."""

    def test_single_resume(self) -> None:
        sections = [Section(SectionType.CONTACT, None, 0, 10, "Jane Doe")]
        assert not detect_multi_resume(sections)

    def test_multiple_contact_blocks(self) -> None:
        sections = [
            Section(SectionType.CONTACT, None, 0, 10, "Jane Doe"),
            Section(SectionType.EXPERIENCE, None, 11, 20, "Work"),
            Section(SectionType.CONTACT, None, 21, 30, "John Doe"),
        ]
        assert detect_multi_resume(sections)


class TestParseCompleteness:
    """Tests for parse completeness computation."""

    def test_complete_resume(self) -> None:
        text = """\
Jane Doe

Experience
Acme Corp | Engineer | 2020 – 2024
- Built Python systems.

Education
BS in CS, 2016

Skills
Python, AWS
"""
        extracted = ExtractedText(text=text, metadata=ExtractionMetadata(method="test"))
        sections = segment_sections(text)
        resume = structure_from_sections(extracted, sections, date(2026, 8, 29))
        from ats_scan.models.resume import CanonicalResume

        canonical = CanonicalResume(
            candidate_id="c_test",
            identity=resume["identity"],
            experience=resume["experience"],
            education=resume["education"],
            skills=resume["skills"],
            timeline=resume["timeline"],
            parse_completeness=None,
        )
        score = compute_parse_completeness(canonical)
        assert 0.0 <= score <= 1.0
        assert score >= 0.5

    def test_empty_resume(self) -> None:
        from ats_scan.models.resume import CanonicalResume

        resume = CanonicalResume(candidate_id="c_empty", parse_completeness=None)
        score = compute_parse_completeness(resume)
        assert score == 0.0


class TestExtractCertifications:
    """Tests for certification extraction."""

    def test_cert_with_expiry(self) -> None:
        text = "AWS Solutions Architect, issued 2020, expires 2023"
        section = Section(
            type=SectionType.CERTIFICATIONS,
            heading=None,
            start=0,
            end=len(text),
            text=text,
        )
        certs = extract_certifications(section)
        assert len(certs) == 1
        assert certs[0].name == text
        assert certs[0].issued == "2020-01-01"
        assert certs[0].expires == "2023-01-01"


class TestExtractProjects:
    """Tests for project extraction."""

    def test_project_with_dates(self) -> None:
        from ats_scan.structure.entities import _extract_projects

        text = "Resume Parser\n- Built a parser.\n2020 – 2021"
        section = Section(
            type=SectionType.PROJECTS,
            heading=None,
            start=0,
            end=len(text),
            text=text,
        )
        projects = _extract_projects(section, date(2026, 8, 29))
        assert len(projects) == 1
        assert projects[0].title == "Resume Parser"
        assert projects[0].start is not None


class TestExperienceVariations:
    """Additional experience parsing coverage."""

    def test_no_dates(self) -> None:
        text = "Acme Corp | Engineer\n- Built things."
        section = Section(
            type=SectionType.EXPERIENCE,
            heading=None,
            start=0,
            end=len(text),
            text=text,
        )
        entries = extract_experience(section, date(2026, 8, 29))
        assert len(entries) == 1
        assert entries[0].employer == "Acme Corp"
        assert entries[0].start is None

    def test_contract_type(self) -> None:
        text = "Acme Corp | Engineer | 2020 – 2021\ncontract"
        section = Section(
            type=SectionType.EXPERIENCE,
            heading=None,
            start=0,
            end=len(text),
            text=text,
        )
        entries = extract_experience(section, date(2026, 8, 29))
        assert entries[0].employment_type == EmploymentType.FULL_TIME


class TestEducationVariations:
    """Additional education parsing coverage."""

    def test_university_first(self) -> None:
        text = "University of Example — BS Computer Science (2016)"
        section = Section(
            type=SectionType.EDUCATION,
            heading=None,
            start=0,
            end=len(text),
            text=text,
        )
        entries = extract_education(section)
        assert len(entries) == 1
        assert entries[0].institution == text
        assert entries[0].end is not None


class TestIdentityVariations:
    """Additional identity extraction coverage."""

    def test_phone_extraction(self) -> None:
        text = "Jane Doe\n+1 555 123 4567"
        section = Section(
            type=SectionType.CONTACT,
            heading=None,
            start=0,
            end=len(text),
            text=text,
        )
        identity = extract_identity(text, section)
        assert identity.full_name == "Jane Doe"
        assert identity.phones == ("+1 555 123 4567",)


def date_value(value: str) -> object:
    from ats_scan.models.resume import DateValue

    return DateValue(value=value)
