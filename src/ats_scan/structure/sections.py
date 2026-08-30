from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from ats_scan.models.source import TextBlock


class SectionType(StrEnum):
    """Heuristic section labels for a resume."""

    CONTACT = "contact"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    PUBLICATIONS = "publications"
    OTHER = "other"


@dataclass(frozen=True)
class Section:
    """A contiguous segment of the resume with a heuristic label."""

    type: SectionType
    heading: str | None
    start: int
    end: int
    text: str
    blocks: tuple[TextBlock, ...] = ()


# Heading patterns used by the heuristic classifier, ordered by specificity.
# Lower index = tested earlier.
_HEADING_PATTERNS: list[tuple[SectionType, re.Pattern[str]]] = [
    (
        SectionType.CONTACT,
        re.compile(
            r"\b(?:contact|info|personal details|reach me)\b",
            re.IGNORECASE,
        ),
    ),
    (
        SectionType.SUMMARY,
        re.compile(
            r"\b(?:summary|objective|about me|professional summary)\b",
            re.IGNORECASE,
        ),
    ),
    (
        SectionType.EXPERIENCE,
        re.compile(
            r"\b(?:experience|employment|work history|professional experience|"
            r"career history|work experience|positions)\b",
            re.IGNORECASE,
        ),
    ),
    (
        SectionType.EDUCATION,
        re.compile(
            r"\b(?:education|academic|qualifications|degrees|university|college)\b",
            re.IGNORECASE,
        ),
    ),
    (
        SectionType.SKILLS,
        re.compile(
            r"\b(?:skills|technical skills|core competencies|technologies|stack|"
            r"expertise|proficiencies)\b",
            re.IGNORECASE,
        ),
    ),
    (
        SectionType.PROJECTS,
        re.compile(
            r"\b(?:projects|personal projects|side projects|open source|portfolio)\b",
            re.IGNORECASE,
        ),
    ),
    (
        SectionType.CERTIFICATIONS,
        re.compile(
            r"\b(?:certifications|certificates|licenses|credentials|accreditations)\b",
            re.IGNORECASE,
        ),
    ),
    (
        SectionType.PUBLICATIONS,
        re.compile(
            r"\b(?:publications|papers|patents|articles|research)\b",
            re.IGNORECASE,
        ),
    ),
]


def _is_heading(line: str) -> bool:
    """Return True if a single line looks like a section heading."""
    stripped = line.strip()
    if not stripped:
        return False
    # Known section heading via regex.
    for _, pattern in _HEADING_PATTERNS:
        if pattern.search(stripped) and len(stripped) <= 40:
            return True
    # Ends with a colon or dash.
    if stripped.endswith(":") or stripped.endswith("-"):
        return True
    # Single short word, but not common content words like a month or role title.
    if len(stripped.split()) == 1 and stripped[0].isalpha() and len(stripped) <= 20:
        return stripped.lower() in _KNOWN_SINGLE_WORD_HEADINGS
    return False


_KNOWN_SINGLE_WORD_HEADINGS: frozenset[str] = frozenset(
    {
        "summary",
        "objective",
        "profile",
        "experience",
        "employment",
        "education",
        "academic",
        "qualifications",
        "skills",
        "technologies",
        "projects",
        "certifications",
        "publications",
        "awards",
        "honors",
        "references",
        "contact",
    }
)


def _classify_heading(heading: str) -> SectionType:
    """Classify a heading into a section type."""
    for section_type, pattern in _HEADING_PATTERNS:
        if pattern.search(heading):
            return section_type
    return SectionType.OTHER


def _paragraphs(text: str) -> list[tuple[int, int, str]]:
    """Split text into paragraphs with (start, end, text) offsets.

    Paragraphs are separated by blank lines. Any line that looks like a section
    heading is also split off into its own paragraph, so that headings that are
    only separated from their content by a single newline still form boundaries.
    """
    raw_blocks: list[tuple[int, int, str]] = []
    start = 0
    for match in re.finditer(r"\n\s*\n", text):
        end = match.start()
        chunk = text[start:end]
        if chunk.strip():
            raw_blocks.append((start, end, chunk))
        start = match.end()
    trailing = text[start:]
    if trailing.strip():
        raw_blocks.append((start, len(text), trailing))

    paragraphs: list[tuple[int, int, str]] = []
    for block_start, _block_end, block_text in raw_blocks:
        lines = block_text.splitlines()
        if not lines:
            continue

        # Compute the offset of each line within the block text.
        line_offsets: list[int] = []
        offset = 0
        for line in lines:
            line_offsets.append(offset)
            offset += len(line) + 1  # +1 for the newline that follows the line

        pending: list[str] = []
        pending_start: int | None = None

        def _flush_pending(text_start: int, text: str) -> None:
            nonlocal pending, pending_start
            if not pending:
                pending_start = None
                return
            content = "\n".join(pending).strip()
            if not content:
                pending = []
                pending_start = None
                return
            if pending_start is None:
                pending_start = text_start
            search_from = pending_start - text_start
            content_offset = text.find(content, search_from)
            if content_offset == -1:
                content_offset = text.find(content)
            if content_offset == -1:
                content_offset = 0
            content_start = text_start + content_offset
            content_end = content_start + len(content)
            paragraphs.append((content_start, content_end, content))
            pending = []
            pending_start = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            if _is_heading(stripped):
                _flush_pending(block_start, block_text)
                heading_offset = line_offsets[i] + line.find(stripped)
                heading_start = block_start + heading_offset
                heading_end = heading_start + len(stripped)
                paragraphs.append((heading_start, heading_end, stripped))
                pending_start = heading_end + 1
            else:
                if not pending:
                    pending_start = block_start + line_offsets[i]
                pending.append(line)
        _flush_pending(block_start, block_text)
    return paragraphs


def segment_sections(text: str, blocks: tuple[TextBlock, ...] = ()) -> list[Section]:
    """Segment resume text into sections using heading patterns and position.

    TRD §3.3 FR-301: sections are contact, summary, experience, education,
    skills, projects, certifications, publications, other.
    """
    paragraphs = _paragraphs(text)
    if not paragraphs:
        return []

    section_starts: list[tuple[int, SectionType, str, int]] = []
    for idx, (start, _end, paragraph) in enumerate(paragraphs):
        if _is_heading(paragraph):
            section_type = _classify_heading(paragraph)
            section_starts.append((idx, section_type, paragraph, start))

    # If no headings were found, infer sections from position.
    if not section_starts:
        return _infer_sections(paragraphs, text, blocks)

    sections: list[Section] = []
    # Infer sub-sections for any text before the first explicit heading.
    first_heading_idx = section_starts[0][0]
    if first_heading_idx > 0:
        leading = paragraphs[:first_heading_idx]
        sections.extend(_infer_leading_sections(leading, text, blocks))

    for i, (_idx, section_type, heading, start) in enumerate(section_starts):
        next_start = section_starts[i + 1][3] if i + 1 < len(section_starts) else len(text)
        heading_end = start + len(heading)
        section_text = text[heading_end:next_start].strip()
        section_blocks = _blocks_in_span(text, blocks, heading_end, next_start)
        sections.append(
            Section(
                type=section_type,
                heading=heading.strip() or None,
                start=start,
                end=next_start,
                text=section_text,
                blocks=section_blocks,
            )
        )

    return sections


def _infer_sections(
    paragraphs: list[tuple[int, int, str]], text: str, blocks: tuple[TextBlock, ...]
) -> list[Section]:
    """Infer sections when no explicit headings are present."""
    if not paragraphs:
        return []

    sections: list[Section] = []
    # First paragraph(s) = contact/summary, last paragraph(s) = education.
    # Everything in between is experience, unless it looks like a skills list.

    first = paragraphs[0]
    sections.append(
        Section(
            type=SectionType.CONTACT,
            heading=None,
            start=first[0],
            end=first[1],
            text=first[2],
            blocks=_blocks_in_span(text, blocks, first[0], first[1]),
        )
    )

    if len(paragraphs) == 1:
        return sections

    # Last paragraph is education only if it looks like education; otherwise infer.
    last = paragraphs[-1]
    middle = paragraphs[1:-1]

    for idx, (start, end, paragraph) in enumerate(middle):
        section_type = _infer_paragraph_type(paragraph, idx, len(middle))
        sections.append(
            Section(
                type=section_type,
                heading=None,
                start=start,
                end=end,
                text=paragraph,
                blocks=_blocks_in_span(text, blocks, start, end),
            )
        )

    last_type = _infer_last_paragraph_type(last[2])
    sections.append(
        Section(
            type=last_type,
            heading=None,
            start=last[0],
            end=last[1],
            text=last[2],
            blocks=_blocks_in_span(text, blocks, last[0], last[1]),
        )
    )
    return sections


def _infer_leading_sections(
    paragraphs: list[tuple[int, int, str]], text: str, blocks: tuple[TextBlock, ...]
) -> list[Section]:
    """Infer section types for paragraphs before the first explicit heading."""
    sections: list[Section] = []
    for idx, (start, end, paragraph) in enumerate(paragraphs):
        if idx == 0:
            section_type = SectionType.CONTACT
        elif _looks_like_skills_list(paragraph):
            section_type = SectionType.SKILLS
        elif re.search(r"^[\s]*[-\*•]", paragraph, re.MULTILINE) or "|" in paragraph:
            section_type = SectionType.EXPERIENCE
        elif _is_heading(paragraph):
            section_type = _classify_heading(paragraph)
        else:
            section_type = SectionType.SUMMARY
        sections.append(
            Section(
                type=section_type,
                heading=None,
                start=start,
                end=end,
                text=paragraph,
                blocks=_blocks_in_span(text, blocks, start, end),
            )
        )
    return sections


def _infer_last_paragraph_type(paragraph: str) -> SectionType:
    """Infer a section type for the final paragraph of a headingless resume."""
    if re.search(r"\b(?:19\d{2}|20\d{2})\b", paragraph) and re.search(
        r"\b(?:BS|BA|MS|MBA|PhD|B\.S\.|M\.S\.|degree|university|college)\b",
        paragraph,
        re.IGNORECASE,
    ):
        return SectionType.EDUCATION
    if _looks_like_skills_list(paragraph):
        return SectionType.SKILLS
    return SectionType.OTHER


def _infer_paragraph_type(paragraph: str, index: int, total: int) -> SectionType:
    """Infer a section type for a single paragraph in the absence of headings."""
    # A comma-separated list of short tokens is treated as skills.
    if _looks_like_skills_list(paragraph):
        return SectionType.SKILLS
    # Bullets strongly indicate experience.
    if re.search(r"^[\s]*[-\*•]", paragraph, re.MULTILINE):
        return SectionType.EXPERIENCE
    # Default to experience for the middle body, summary for the first paragraph after contact.
    if index == 0 and total > 1:
        return SectionType.SUMMARY
    return SectionType.EXPERIENCE


def _looks_like_skills_list(text: str) -> bool:
    """Return True if the paragraph (or any line in it) is a comma-separated skills list."""
    stripped = text.strip()
    if not stripped:
        return False
    # If any single line is a comma-separated list of short tokens, treat it as skills.
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        items = [item.strip() for item in re.split(r"[,;]", line)]
        if len(items) < 2:
            continue
        short = sum(
            1 for item in items if len(item.split()) <= 3 and any(c.isalnum() for c in item)
        )
        if short / len(items) >= 0.7:
            return True
    return False


def _blocks_in_span(
    text: str, blocks: tuple[TextBlock, ...], start: int, end: int
) -> tuple[TextBlock, ...]:
    """Return blocks whose text falls inside the given character span."""
    span_text = text[start:end]
    result: list[TextBlock] = []
    cursor = 0
    for block in blocks:
        bt = block.text
        if not bt:
            continue
        pos = span_text.find(bt, cursor)
        if pos != -1:
            result.append(block)
            cursor = pos + len(bt)
    return tuple(result)
