from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from resume_ranker.structure.sections import Section, SectionType

_SKILLS_SCANNER_REGEX: re.Pattern[str] | None = None


def _default_ontology_path() -> Path:
    """Return the default ontology data directory relative to the project root."""
    # src/resume_ranker/structure/skills_scanner.py -> project root is three levels up.
    return Path(__file__).resolve().parents[3] / "data" / "ontology" / "2026.07"


def _supplemental_acronyms_path() -> Path:
    """Return the path to the supplemental acronym list shipped with C-08."""
    return Path(__file__).resolve().parent / "data" / "scan_acronyms.txt"


def _load_scan_patterns() -> list[str]:
    """Load all skill patterns from the ontology and the supplemental acronym file."""
    patterns: set[str] = set()

    ontology_file = _default_ontology_path() / "skills.json"
    if ontology_file.exists():
        raw = json.loads(ontology_file.read_text(encoding="utf-8"))
        for item in raw.get("skills", []):
            canonical = item.get("canonical", "").strip().lower()
            if canonical:
                patterns.add(canonical)
            for alias in item.get("aliases", []):
                alias = alias.strip().lower()
                if alias:
                    patterns.add(alias)

    acronyms_file = _supplemental_acronyms_path()
    if acronyms_file.exists():
        for line in acronyms_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.add(line.lower())

    # Sort by length descending so the regex engine prefers longer matches at each
    # position (e.g. "TCP/IP" before "TCP").
    return sorted(patterns, key=len, reverse=True)


def _build_scanner_regex() -> re.Pattern[str]:
    """Compile a single regex that matches any known skill phrase with word boundaries."""
    patterns = _load_scan_patterns()
    if not patterns:
        # Never matches; allows the rest of the code to assume a regex exists.
        return re.compile(r"(?!)", re.IGNORECASE)

    escaped = [re.escape(p) for p in patterns]
    # Boundaries around [a-z0-9+#] work for normal words and for tokens like C++,
    # C#, TCP/IP, etc. without letting a short token match inside a longer one.
    regex = r"(?<![a-z0-9+#])(?:" + "|".join(escaped) + r")(?![a-z0-9+#])"
    return re.compile(regex, re.IGNORECASE)


def _scanner_regex() -> re.Pattern[str]:
    """Return the cached compiled scanner regex, building it on first call."""
    global _SKILLS_SCANNER_REGEX
    if _SKILLS_SCANNER_REGEX is None:
        _SKILLS_SCANNER_REGEX = _build_scanner_regex()
    return _SKILLS_SCANNER_REGEX


def _section_for_span(sections: Sequence[Section], start: int, end: int) -> Section | None:
    """Return the section that contains the given character span, if any."""
    for section in sections:
        if section.start <= start < section.end or section.start < end <= section.end:
            return section
    return None


def scan_text_for_skills(
    text: str, sections: Sequence[Section]
) -> list[tuple[str, tuple[int, int], str]]:
    """Scan the full resume text for known skill phrases.

    Returns a list of ``(raw_text, span, section_type)`` tuples. Matches inside the
    contact section are skipped because those blocks are identity information, not
    skill evidence.
    """
    regex = _scanner_regex()
    matches: list[tuple[str, tuple[int, int], str]] = []
    for match in regex.finditer(text):
        start, end = match.span()
        section = _section_for_span(sections, start, end)
        if section is not None and section.type == SectionType.CONTACT:
            continue
        section_type = section.type if section is not None else SectionType.SUMMARY
        matches.append((match.group(0), (start, end), section_type))
    return matches
