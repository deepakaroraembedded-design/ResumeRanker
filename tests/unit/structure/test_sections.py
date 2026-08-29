from __future__ import annotations

from ats_scan.structure.sections import SectionType, segment_sections

SAMPLE_RESUME = """\
Jane Doe
jane.doe@example.com | +1 555 123 4567

Summary
Experienced software engineer focused on backend systems and Python.

Experience
Acme Corp | Senior Software Engineer | 2020 – 2024
- Led migration to Python and improved reliability by 50%.

Education
BS in Computer Science, University of Example, 2016

Skills
Python, AWS, Docker, Kubernetes

Certifications
AWS Certified Solutions Architect, 2020
"""


class TestSegmentSections:
    """Tests for resume section segmentation per TRD §3.3 FR-301."""

    def test_detects_all_major_sections(self) -> None:
        sections = segment_sections(SAMPLE_RESUME)
        types = [s.type for s in sections]
        assert SectionType.CONTACT in types
        assert SectionType.SUMMARY in types
        assert SectionType.EXPERIENCE in types
        assert SectionType.EDUCATION in types
        assert SectionType.SKILLS in types
        assert SectionType.CERTIFICATIONS in types

    def test_headings_are_classified(self) -> None:
        sections = segment_sections(SAMPLE_RESUME)
        by_type = {s.type: s for s in sections}
        assert by_type[SectionType.EXPERIENCE].heading == "Experience"
        assert by_type[SectionType.EDUCATION].heading == "Education"

    def test_spans_cover_full_text(self) -> None:
        sections = segment_sections(SAMPLE_RESUME)
        first_start = min(s.start for s in sections)
        last_end = max(s.end for s in sections)
        assert first_start == 0
        assert last_end == len(SAMPLE_RESUME)

    def test_no_headings_inferred(self) -> None:
        text = """\
Software Engineer

Python, AWS, Docker

Acme Corp | Python | 2020 – 2024
- Built Python systems.

BS in Computer Science, 2016
"""
        sections = segment_sections(text)
        types = [s.type for s in sections]
        assert SectionType.CONTACT in types
        assert SectionType.EXPERIENCE in types
        assert SectionType.EDUCATION in types
        assert SectionType.SKILLS in types

    def test_unknown_heading_is_other(self) -> None:
        text = "Hobbies:\n\nReading, hiking"
        sections = segment_sections(text)
        assert sections[0].type == SectionType.OTHER

    def test_publications_heading(self) -> None:
        text = "Publications\n\nPaper on AI."
        sections = segment_sections(text)
        assert sections[0].type == SectionType.PUBLICATIONS

    def test_projects_heading(self) -> None:
        text = "Projects\n\nOpen source parser."
        sections = segment_sections(text)
        assert sections[0].type == SectionType.PROJECTS

    def test_empty_text(self) -> None:
        assert segment_sections("") == []

    def test_uppercase_heading(self) -> None:
        text = "WORK EXPERIENCE\n\nEngineer at Acme"
        sections = segment_sections(text)
        assert sections[0].type == SectionType.EXPERIENCE

    def test_colon_heading(self) -> None:
        text = "Education:\n\nBS in CS"
        sections = segment_sections(text)
        assert sections[0].type == SectionType.EDUCATION

    def test_no_headings_last_is_education(self) -> None:
        text = "Jane Doe\n\nAcme Corp | Engineer | 2020 – 2024\n- Built things.\n\nBS in CS, University of Example, 2016"
        sections = segment_sections(text)
        assert sections[-1].type == SectionType.EDUCATION

    def test_no_headings_last_is_other(self) -> None:
        text = "Jane Doe\n\nAcme Corp | Engineer | 2020 – 2024\n- Built things.\n\nSome unrelated text."
        sections = segment_sections(text)
        assert sections[-1].type == SectionType.OTHER

    def test_blocks_in_span(self) -> None:
        from ats_scan.models.source import TextBlock

        text = "Contact\n\nJane Doe\n\nExperience\n\nAcme Corp"
        blocks = (TextBlock(text="Jane Doe", page=0, bbox=(0, 0, 1, 1)),)
        sections = segment_sections(text, blocks)
        contact = next(s for s in sections if s.type == SectionType.CONTACT)
        assert len(contact.blocks) == 1
        assert contact.blocks[0].text == "Jane Doe"
