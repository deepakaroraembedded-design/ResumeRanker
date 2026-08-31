from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final, TypedDict

from resume_ranker.models.resume import (
    Bullet,
    Certification,
    DatePrecision,
    DateValue,
    EducationEntry,
    ExperienceEntry,
    Identity,
    ProjectEntry,
    SkillMention,
    Timeline,
)
from resume_ranker.models.source import ExtractedText
from resume_ranker.structure.dates import calendar_union, month_range, parse_date_range
from resume_ranker.structure.sections import Section, SectionType, _looks_like_skills_list
from resume_ranker.structure.skills_scanner import scan_text_for_skills

_EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,5}[\s\-]?\d{3,5}"
)


# Curated token list used to recognise skill mentions in heuristic mode.
# Heuristic structuring does not depend on the full ontology (C-04); it only
# needs to demonstrate that skills can be harvested from all sections and tagged
# with provenance. The list covers the skills appearing in the synthetic corpus.
_HEURISTIC_SKILLS: Final[frozenset[str]] = frozenset(
    {
        "agile",
        "airflow",
        "aws",
        "bash",
        "confluence",
        "cypress",
        "dbt",
        "docker",
        "git",
        "java",
        "javascript",
        "jenkins",
        "jira",
        "kafka",
        "kubernetes",
        "linux",
        "node.js",
        "nodejs",
        "node",
        "playwright",
        "pytest",
        "python",
        "react",
        "roadmapping",
        "scrum",
        "selenium",
        "spark",
        "sql",
        "tableau",
        "terraform",
        "typescript",
        "c++",
        "go",
        "rust",
        "php",
        "ruby",
        "scala",
    }
)


# Tokens treated as noise when a comma/bullet skills list is expanded in a
# dedicated skills section.  This is intentionally conservative: a token that is
# not a stop word is kept as a candidate skill and downstream ontology matching
# decides whether it is meaningful.
_SKILLS_LIST_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "by",
        "for",
        "from",
        "has",
        "have",
        "having",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "with",
        "via",
        "using",
        "such",
        "like",
        "including",
        "etc",
        "eg",
        "ie",
        "etc.",
        "e.g",
        "i.e",
        "e.g.",
        "i.e.",
        "and/or",
        "both",
        "either",
        "neither",
        "nor",
        "not",
        "but",
        "also",
        "plus",
        "various",
        "other",
        "others",
        "another",
        "all",
        "any",
        "some",
        "many",
        "much",
        "more",
        "most",
        "few",
        "several",
        "every",
        "each",
        "one",
        "two",
        "three",
    }
)


# Section labels that count toward parse completeness.
_REQUIRED_SECTIONS: Final[frozenset[str]] = frozenset(
    {
        SectionType.EXPERIENCE,
        SectionType.EDUCATION,
        SectionType.SKILLS,
    }
)


def _now_from_iso(now_str: str | None) -> date:
    """Convert an ISO-8601 date string (e.g. from RunContext.now) to a date."""
    if not now_str:
        return date.today()
    try:
        return date.fromisoformat(now_str)
    except ValueError:
        return datetime.fromisoformat(now_str).date()


def extract_identity(text: str, section: Section | None) -> Identity:
    """Extract a minimal Identity from the contact section.

    No field is fabricated: fields that cannot be found are left as None.
    """
    source = section.text if section else text
    emails = tuple(sorted(set(_EMAIL_RE.findall(source))))
    phones = tuple(sorted(set(_PHONE_RE.findall(source))))
    # Name is the first non-empty line, if the contact section is short.
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    name: str | None = None
    if (
        section
        and section.type == SectionType.CONTACT
        and lines
        and len(lines) <= 4
        or not section
        and lines
        and len(lines) <= 2
    ):
        name = lines[0]
    return Identity(full_name=name, emails=emails, phones=phones)


_ROLE_HEADER_RE = re.compile(
    r"^.*\|.*(?:19\d{2}|20\d{2}).*(?:[-\u2013\u2014\u2015]|to|through).*(?:19\d{2}|20\d{2}|present|current|now|till date)",
    re.IGNORECASE,
)


# Optional month, year, dash, optional month, year-or-present.
_DATE_RANGE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"(?:19|20)\d{2}\s*[-\u2013\u2014\u2015]\s*"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"(?:(?:19|20)\d{2}|present|current|now|till date)",
    re.IGNORECASE,
)


def _looks_like_role_header(line: str) -> bool:
    """Return True if a line looks like a role header with dates."""
    stripped = line.strip()
    if not stripped:
        return False
    if "|" in stripped and re.search(r"(?:19\d{2}|20\d{2})", stripped):
        return True
    return bool(_DATE_RANGE_RE.search(stripped))


def _extract_experience_lines(text: str) -> list[str]:
    """Split an experience section into candidate role blocks.

    Role headers are lines like "Employer | Title | 2020 – 2025" or lines that
    contain a date range. Each header starts a new block; bullets following the
    header belong to that role.
    """
    lines = text.splitlines()
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _looks_like_role_header(stripped):
            if current:
                blocks.append("\n".join(current))
            current = [stripped]
        else:
            current.append(stripped)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _split_employer_location(text: str) -> tuple[str, str | None]:
    """Split an employer string like 'Verizon — Irving, TX' into employer and location."""
    if " — " in text:
        employer, location = text.split(" — ", 1)
        return employer.strip(), location.strip()
    if re.search(r"\s+[-\u2013\u2014\u2015]\s+", text):
        employer, location = re.split(r"\s+[-\u2013\u2014\u2015]\s+", text, maxsplit=1)
        return employer.strip(), location.strip()
    return text.strip(), None


def _looks_like_employer(text: str) -> bool:
    """Heuristic to decide whether a segment is more likely an employer than a title."""
    lower = text.lower()
    return bool(
        re.search(
            r"\b(inc\.?|corp\.?|corporation|llc|ltd\.?|limited|company|gmbh|plc|technologies)\b",
            lower,
        )
    ) or text.rstrip(".").lower().endswith((".com", ".org", ".io"))


def _parse_role_header(header: str) -> dict[str, str | None]:
    """Parse a role header into employer, title, and dates.

    Handles the canonical form "Employer | Title | 2020 – 2025" as well as the
    common resume form "Title | Employer — Location 2020 – 2025" and the
    bullet form "Title, Employer (2020 – 2025)".
    """
    # Try the canonical three-pipe form first.
    parts = [part.strip() for part in re.split(r"\s*\|\s*", header)]
    if len(parts) == 3:
        return {"employer": parts[0], "title": parts[1], "dates": parts[2]}

    if len(parts) == 2:
        # Default: title | employer-location-dates.
        title = parts[0]
        remainder = parts[1]
        date_match = _DATE_RANGE_RE.search(remainder)
        if date_match:
            dates = date_match.group(0)
            employer_loc = remainder[: date_match.start()].strip().rstrip(",—")
        else:
            dates = None
            employer_loc = remainder
        # If the first segment looks like an employer, swap the default order.
        if _looks_like_employer(parts[0]) and not _looks_like_employer(parts[1]):
            title, employer_loc = parts[1], parts[0]
        employer, _location = _split_employer_location(employer_loc)
        return {"employer": employer, "title": title, "dates": dates}

    # No pipe: try to extract a date and split by comma.
    date_match = _DATE_RANGE_RE.search(header)
    if date_match:
        dates = date_match.group(0)
        before = header[: date_match.start()].strip()
        # Remove a parenthesised date fragment if it was left over.
        before = re.sub(r"\s*\([^)]*\)\s*$", "", before).strip()
        if "," in before:
            title, employer = [p.strip() for p in before.split(",", 1)]
            return {"employer": employer, "title": title, "dates": dates}
        return {"employer": None, "title": before, "dates": dates}

    return {"employer": None, "title": header, "dates": None}


def _extract_bullets(text: str, parent_offset: int) -> tuple[Bullet, ...]:
    """Extract bullet lines from a block of text with char offsets."""
    bullets: list[Bullet] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        content = stripped[1:].strip() if stripped.startswith(("-", "•", "*")) else stripped
        pos = text.find(line)
        span: tuple[int, int] | None = None
        if pos != -1:
            start = parent_offset + pos + (len(line) - len(content))
            end = start + len(content)
            span = (start, end)
        bullets.append(Bullet(text=content, span=span))
    return tuple(bullets)


def extract_experience(section: Section, now: date) -> tuple[ExperienceEntry, ...]:
    """Extract experience entries from a section.

    FR-302: employer, title, location, dates, employment type, bullets.
    """
    blocks = _extract_experience_lines(section.text)
    entries: list[ExperienceEntry] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        header = lines[0]
        parsed = _parse_role_header(header)
        employer = parsed.get("employer") or None
        title = parsed.get("title") or None
        dates_text = parsed.get("dates") or None
        bullets = _extract_bullets("\n".join(lines[1:]), section.start + len(header) + 1)
        start_date: DateValue | None = None
        end_date: DateValue | None = None
        months: int | None = None
        if dates_text:
            range_pair = parse_date_range(str(dates_text), now=now)
            if range_pair:
                start_date, end_date = range_pair
                months = month_range(start_date, end_date, now)
        entry = ExperienceEntry(
            employer=employer,
            title_raw=title,
            start=start_date,
            end=end_date,
            months=months,
            bullets=bullets,
            span=(section.start, section.end),
        )
        entries.append(entry)
    return tuple(entries)


def extract_education(section: Section) -> tuple[EducationEntry, ...]:
    """Extract education entries from a section.

    FR-309: institution, degree level, field of study, graduation date, honours.
    Handles both line-per-entry layouts and compact layouts where multiple
    entries are separated by middle-dot or bullet characters.
    """
    entries: list[EducationEntry] = []
    # Split on newlines, middle dots, and common bullet separators.
    raw_entries = re.split(r"[\n\r]+|\s*[·•●]\s*", section.text)
    for entry in raw_entries:
        entry = entry.strip()
        if not entry or entry.lower() == "education":
            continue

        institution: str | None = None
        degree_level: str | None = None
        field: str | None = None
        grad_year: DateValue | None = None

        # Pattern: "MCA, Master of Computer Applications — GGSIP University (2004)"
        match = re.match(
            r"(?P<degree>[^,·•]+),\s*(?P<field>[^—–-]+?)\s*[—–-]\s*"
            r"(?P<inst>[^()]+?)\s*\((?P<year>\d{4})\)",
            entry,
        )
        if not match:
            # Pattern: "B.Sc. Mathematics — Hansraj College, Delhi University (2001)".
            # The degree token must be all-uppercase or dotted, so we do not
            # accidentally match an institution-first entry.
            match = re.match(
                r"(?P<degree>[A-Z][A-Z\.]{0,5})\s+(?P<field>[^—–-]+?)\s*[—–-]\s*"
                r"(?P<inst>[^()]+?)\s*\((?P<year>\d{4})\)",
                entry,
            )
        if not match:
            # Pattern: "BS in Computer Science, University of Example, 2016"
            match = re.match(
                r"(?P<degree>[A-Z\.]+)\s+(?:in\s+)?(?P<field>[^,]+),\s+"
                r"(?P<inst>[^,]+)(?:,\s+(?P<year>\d{4}))?",
                entry,
            )
        if match:
            degree_level = match.group("degree").strip()
            field = match.group("field").strip()
            institution = match.group("inst").strip()
            year_str = match.group("year")
            if year_str:
                grad_year = DateValue(value=f"{year_str}-01-01", precision=DatePrecision.YEAR)
        else:
            # Fallback: keep the whole entry as the institution and look for a year.
            institution = entry
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", entry)
            if year_match:
                grad_year = DateValue(
                    value=f"{year_match.group(1)}-01-01",
                    precision=DatePrecision.YEAR,
                )
        entries.append(
            EducationEntry(
                institution=institution,
                degree_level=degree_level,
                field=field,
                end=grad_year,
                span=(section.start, section.end),
            )
        )
    return tuple(entries)


def extract_certifications(section: Section) -> tuple[Certification, ...]:
    """Extract certifications from a section.

    FR-309: name, issuer, issue date, expiry date, credential ID where present.
    """
    certs: list[Certification] = []
    for line in section.text.splitlines():
        line = line.strip()
        if not line or line.lower() == "certifications":
            continue
        issued: str | None = None
        expires: str | None = None
        issuer: str | None = None
        name = line
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", line)
        if year_match:
            issued = f"{year_match.group(1)}-01-01"
        # Heuristic expiry: look for "expires" or "valid until".
        expiry_match = re.search(
            r"(?:expires?|valid until|exp)\s*:?\s*(?P<year>\d{4})", line, re.IGNORECASE
        )
        if expiry_match:
            expires = f"{expiry_match.group('year')}-01-01"
        certs.append(
            Certification(
                name=name,
                issuer=issuer,
                issued=issued,
                expires=expires,
                span=(section.start, section.end),
            )
        )
    return tuple(certs)


def _skill_tokens(text: str) -> list[str]:
    """Return candidate raw skill tokens from a sentence.

    The heuristic skill set is used for recognition, but the raw token as it
    appears in the source text is returned so that downstream ontology
    canonicalisation can operate on the original form.
    """
    tokens: list[str] = []
    for raw in re.split(r"[,;\s()]+", text):
        raw = raw.strip()
        normalized = raw.lower().rstrip(".")
        if normalized in _HEURISTIC_SKILLS:
            tokens.append(raw)
    return tokens


def _skill_tokens_from_list(text: str) -> list[str]:
    """Extract candidate raw skills from a comma/bullet skills list line.

    Category labels such as "Kernel, Datapath & Networking:" are stripped.
    Items are split by common delimiters; stop words and obvious noise are
    dropped.  The ontology layer (C-04) later decides which candidates are real
    skills, so this function is intentionally permissive.
    """
    if ":" in text:
        text = text.split(":", 1)[1]

    items = re.split(r"[,;·•&/]|(?:\s+\band\b\s+)|(?:\s+&\s+)", text)
    results: list[str] = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        item = re.sub(r"\s+", " ", item).rstrip(".")
        if not item:
            continue
        cleaned = re.sub(r"[^a-z0-9+#]", "", item.lower())
        if cleaned.isdigit() or not cleaned:
            continue
        if len(cleaned) < 2 and cleaned not in {"c", "r", "go"}:
            continue
        if cleaned in _SKILLS_LIST_STOP_WORDS:
            continue
        results.append(item)
    return results


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, sentence) spans for a piece of text."""
    sentences: list[tuple[int, int, str]] = []
    cursor = 0
    for match in re.finditer(r"[^.!?\n]+[.!?]?", text):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        start = text.find(sentence, cursor)
        if start == -1:
            start = match.start()
        end = start + len(sentence)
        sentences.append((start, end, sentence))
        cursor = end
    return sentences


def _token_abs_span(
    sentence: str, token: str, sent_start: int, section_start: int
) -> tuple[int, int]:
    """Return the absolute resume span of *token* as it appears in *sentence*.

    The sentence span is already relative to the section start. If the token is
    not found (e.g. it was normalised away), fall back to the whole sentence.
    """
    offset = sentence.find(token)
    if offset == -1:
        return (section_start + sent_start, section_start + sent_start + len(sentence))
    abs_start = section_start + sent_start + offset
    return abs_start, abs_start + len(token)


def _sentence_for_span(text: str, start: int, end: int) -> str:
    """Return the sentence that contains the character span [start, end).

    The search expands outward to the nearest sentence boundary (``.``, ``!``,
    ``?`` or newline). If no boundary is found the whole text is returned.
    """
    sent_start = start
    while sent_start > 0 and text[sent_start - 1] not in ".!?\n":
        sent_start -= 1
    sent_end = end
    while sent_end < len(text) and text[sent_end] not in ".!?\n":
        sent_end += 1
    return text[sent_start:sent_end].strip()


@dataclass
class _SkillHarvest:
    """Accumulator for one skill mention across a resume."""

    sections: set[str] = field(default_factory=set)
    mentions: int = 0
    evidence_spans: list[tuple[int, int]] = field(default_factory=list)
    first_used: str | None = None
    last_used: str | None = None


def extract_skills(text: str, sections: list[Section]) -> tuple[SkillMention, ...]:
    """Harvest skills from all sections, recording provenance and sentence context.

    FR-308: skills are extracted from all sections, with section provenance and
    the surrounding sentence stored for downstream evidence.
    """
    by_skill: dict[str, _SkillHarvest] = defaultdict(_SkillHarvest)
    for section in sections:
        for sent_start, _sent_end, sentence in _sentence_spans(section.text):
            is_skills_list = section.type == SectionType.SKILLS and _looks_like_skills_list(
                sentence
            )
            tokens = (
                _skill_tokens_from_list(sentence) if is_skills_list else _skill_tokens(sentence)
            )
            for token in tokens:
                entry = by_skill[token]
                entry.sections.add(str(section.type))
                entry.mentions += 1
                entry.evidence_spans.append(
                    _token_abs_span(sentence, token, sent_start, section.start)
                )
                if entry.first_used is None:
                    entry.first_used = sentence
                entry.last_used = sentence

    # Full-text scan for known skill phrases that the token-based harvest misses
    # (acronyms, multi-word phrases, and tokens not separated by commas in skills
    # lists). The scanner is anchored to the same text and sections so evidence
    # spans remain valid. Matches are merged into any existing entry for the same
    # raw token so that additional provenance is accumulated.
    for raw, span, section_type in scan_text_for_skills(text, sections):
        entry = by_skill[raw]
        entry.sections.add(str(section_type))
        entry.mentions += 1
        entry.evidence_spans.append(span)
        sentence = _sentence_for_span(text, *span)
        if entry.first_used is None:
            entry.first_used = sentence
        entry.last_used = sentence

    mentions: list[SkillMention] = []
    for raw, data in by_skill.items():
        mentions.append(
            SkillMention(
                raw=raw,
                sections=tuple(sorted(data.sections)),
                mentions=data.mentions,
                first_used=data.first_used,
                last_used=data.last_used,
                evidence_spans=tuple(data.evidence_spans),
            )
        )
    return tuple(mentions)


def build_timeline(experience: tuple[ExperienceEntry, ...]) -> Timeline:
    """Build a calendar-union timeline from experience entries.

    FR-304: total months covered never double counts overlapping roles. Contract
    roles are retained but contribute to the union like any other role.
    """
    intervals: list[tuple[int, int]] = []
    for entry in experience:
        start_month = None
        end_month = None
        if entry.start and entry.start.value:
            start_month = _month_from_iso(entry.start.value)
        if entry.end and entry.end.value:
            end_month = _month_from_iso(entry.end.value)
        if start_month is not None and end_month is not None:
            intervals.append((start_month, end_month))
    total = calendar_union(intervals)
    tenures: list[int] = []
    for entry in experience:
        if entry.months:
            tenures.append(entry.months)
    median_tenure = int(sorted(tenures)[len(tenures) // 2]) if tenures else None
    return Timeline(
        total_months_covered=total,
        role_count=len(experience),
        median_tenure_months=median_tenure,
    )


def _month_from_iso(value: str) -> int | None:
    """Return months-since-epoch for an ISO date string."""
    try:
        dt = date.fromisoformat(value)
    except ValueError:
        try:
            dt = datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return dt.year * 12 + (dt.month - 1)


def detect_multi_resume(sections: list[Section]) -> bool:
    """Return True if multiple distinct contact/identity blocks are detected."""
    contact_count = sum(1 for section in sections if section.type == SectionType.CONTACT)
    # A repeated name block in the middle of the document also counts.
    name_like_blocks = 0
    for section in sections:
        if section.type in {SectionType.CONTACT, SectionType.SUMMARY}:
            lines = [line.strip() for line in section.text.splitlines() if line.strip()]
            if len(lines) <= 2 and any(" " in line for line in lines):
                name_like_blocks += 1
    return contact_count > 1 or name_like_blocks > 1


def compute_parse_completeness(
    resume: object,  # CanonicalResume not imported to avoid circularity
) -> float:
    """Compute a rough parse completeness score in [0, 1].

    Completeness is based on the presence of major sections (experience,
    education, skills) and the fraction of experience entries that have both
    employer and dates resolved.
    """
    # Avoid importing CanonicalResume directly at module level to keep the
    # import graph simple. Use attribute access.
    sections_found: set[str] = set()
    if getattr(resume, "experience", None):
        sections_found.add("experience")
    if getattr(resume, "education", None):
        sections_found.add("education")
    if getattr(resume, "skills", None):
        sections_found.add("skills")

    section_score = len(sections_found) / len(_REQUIRED_SECTIONS)

    experience = getattr(resume, "experience", ())
    if not experience:
        return round(section_score * 0.7, 2)

    complete_entries = 0
    for entry in experience:
        if entry.employer and entry.start and entry.start.value:
            complete_entries += 1
    entry_score = complete_entries / len(experience)
    return round((section_score * 0.5) + (entry_score * 0.5), 2)


class _ResumeFields(TypedDict, total=False):
    """Typed result of heuristic field extraction."""

    identity: Identity | None
    experience: tuple[ExperienceEntry, ...]
    education: tuple[EducationEntry, ...]
    certifications: tuple[Certification, ...]
    skills: tuple[SkillMention, ...]
    projects: tuple[ProjectEntry, ...]
    timeline: Timeline


def structure_from_sections(
    text: ExtractedText, sections: list[Section], now: date
) -> _ResumeFields:
    """Build the canonical fields from a list of sections.

    Returns a dictionary of keyword arguments that can be passed to build a
    CanonicalResume. This function is deterministic and does not fabricate fields.
    """
    contact_section = next((s for s in sections if s.type == SectionType.CONTACT), None)
    identity = extract_identity(text.text, contact_section)

    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    certifications: list[Certification] = []
    projects: list[ProjectEntry] = []
    for section in sections:
        if section.type == SectionType.EXPERIENCE:
            experience.extend(extract_experience(section, now))
        elif section.type == SectionType.EDUCATION:
            education.extend(extract_education(section))
        elif section.type == SectionType.CERTIFICATIONS:
            certifications.extend(extract_certifications(section))
        elif section.type == SectionType.PROJECTS:
            projects.extend(_extract_projects(section, now))

    skills = extract_skills(text.text, sections)
    timeline = build_timeline(tuple(experience))
    return {
        "identity": identity,
        "experience": tuple(experience),
        "education": tuple(education),
        "certifications": tuple(certifications),
        "skills": skills,
        "projects": tuple(projects),
        "timeline": timeline,
    }


def _extract_projects(section: Section, now: date) -> tuple[ProjectEntry, ...]:
    """Extract project entries from a projects section."""
    projects: list[ProjectEntry] = []
    for block in re.split(r"\n\s*\n", section.text):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        title = lines[0].strip() if lines else None
        bullets = _extract_bullets("\n".join(lines[1:]), section.start + len(title or "") + 1)
        # Try to find a date range in the title or first bullet.
        dates_text = None
        for line in lines:
            match = re.search(r"\d{4}\s*[\-–]\s*(?:\d{4}|present|current)", line, re.IGNORECASE)
            if match:
                dates_text = match.group(0)
                break
        start: DateValue | None = None
        end: DateValue | None = None
        months: int | None = None
        if dates_text:
            range_pair = parse_date_range(dates_text, now=now)
            if range_pair:
                start, end = range_pair
                months = month_range(start, end, now)
        projects.append(
            ProjectEntry(
                title=title,
                start=start,
                end=end,
                months=months,
                bullets=bullets,
                span=(section.start, section.end),
            )
        )
    return tuple(projects)
