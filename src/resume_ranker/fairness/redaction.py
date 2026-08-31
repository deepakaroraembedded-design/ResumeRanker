from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from resume_ranker.models.common import ReidentificationMap
from resume_ranker.models.resume import (
    CanonicalResume,
    DatePrecision,
    DateValue,
    EducationEntry,
    ExperienceEntry,
    Identity,
    Location,
    ProjectEntry,
)
from resume_ranker.models.source import SourceDocument

_REDACTED = "[REDACTED]"
_REDACTED_PATH = "redacted"


class BlindRedactor:
    """Redactor that removes identity-revealing attributes from a resume.

    Implements the :class:`resume_ranker.protocols.Redactor` protocol.  Blind mode
    is the default per TRD §11.1.  In non-blind mode the resume is returned
    unchanged and the sidecar is empty.
    """

    def __init__(self, blind: bool = True) -> None:
        self._blind = blind

    def redact(self, resume: CanonicalResume) -> tuple[CanonicalResume, ReidentificationMap]:
        """Redact identity attributes and return the redacted resume plus a
        re-identification sidecar mapping."""
        if not self._blind:
            return resume, {}
        mapping: ReidentificationMap = {}
        redacted = _redact_resume(resume, mapping)
        return redacted, mapping


def write_reidentification_sidecar(
    mapping: ReidentificationMap, path: Path, mode: int = 0o600
) -> None:
    """Write the re-identification sidecar to *path* with restrictive
    permissions."""
    path.write_text(
        json.dumps(dict(mapping), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    path.chmod(mode)


def redact_text(text: str, mapping: ReidentificationMap) -> str:
    """Redact any values from *mapping* that appear in *text*.

    Useful for scrubbing identity strings from model prompts before they are
    sent to an LLM (TRD §11.1, FR-507).
    """
    if not mapping:
        return text
    # Replace longest values first so that shorter substrings do not leave
    # fragments of longer values behind.
    originals = sorted(
        (value for value in mapping.values() if value and value != _REDACTED),
        key=len,
        reverse=True,
    )
    redacted = text
    for original in originals:
        redacted = redacted.replace(original, _REDACTED)
    return redacted


def _redact_resume(resume: CanonicalResume, mapping: ReidentificationMap) -> CanonicalResume:
    """Build a redacted copy of *resume* and populate *mapping*."""
    updates: dict[str, Any] = {}
    reference_year = _earliest_role_year(resume)

    if resume.identity is not None:
        updates["identity"] = _redact_identity(resume.identity, mapping)

    if resume.source is not None:
        updates["source"] = _redact_source(resume.source, resume.candidate_id, mapping)

    if resume.education:
        updates["education"] = _redact_education(resume.education, mapping, reference_year)

    if resume.experience:
        updates["experience"] = _redact_experience(resume.experience, mapping)

    if resume.projects:
        updates["projects"] = _redact_projects(resume.projects, mapping)

    if resume.summary:
        updates["summary"] = _redact_summary(resume.summary, mapping)

    return resume.model_copy(deep=True, update=updates)


def _redact_identity(identity: Identity, mapping: ReidentificationMap) -> Identity:
    """Redact all fields of an Identity block."""
    if identity.full_name:
        mapping["identity.full_name"] = identity.full_name

    if identity.emails:
        mapping["identity.emails"] = ", ".join(identity.emails)

    if identity.phones:
        mapping["identity.phones"] = ", ".join(identity.phones)

    for key, value in (identity.links or {}).items():
        if value:
            mapping[f"identity.links.{key}"] = value

    redacted_location = _redact_location(identity.location, mapping, "identity.location")

    return Identity(
        full_name=None,
        emails=(),
        phones=(),
        links={},
        location=redacted_location,
    )


def _redact_location(
    location: Location | None, mapping: ReidentificationMap, prefix: str
) -> Location | None:
    """Redact a Location block, keeping only country if it is needed for
    work-authorisation knockouts."""
    if location is None:
        return None

    if location.city:
        mapping[f"{prefix}.city"] = location.city
    if location.region:
        mapping[f"{prefix}.region"] = location.region
    if location.country:
        mapping[f"{prefix}.country"] = location.country

    return Location(
        city=None,
        region=None,
        country=None,
        remote=location.remote,
    )


def _redact_source(
    source: SourceDocument, candidate_id: str, mapping: ReidentificationMap
) -> SourceDocument:
    """Redact the file-system path in a SourceDocument."""
    mapping["source.path"] = source.path
    return source.model_copy(
        deep=True,
        update={"path": f"{candidate_id}/{_REDACTED_PATH}"},
    )


def _redact_education(
    entries: tuple[EducationEntry, ...],
    mapping: ReidentificationMap,
    reference_year: int | None,
) -> tuple[EducationEntry, ...]:
    """Redact institution names and graduation years from education entries."""
    redacted: list[EducationEntry] = []
    for index, entry in enumerate(entries):
        updates: dict[str, Any] = {}

        if entry.institution:
            mapping[f"education.{index}.institution"] = entry.institution
            updates["institution"] = None

        if entry.end is not None and entry.end.value:
            mapping[f"education.{index}.end"] = entry.end.value
            interval = _graduation_interval(entry.end, reference_year)
            if interval is not None:
                mapping[f"education.{index}.end_interval_to_first_role"] = interval
            updates["end"] = DateValue(value=None, precision=DatePrecision.UNKNOWN)

        if entry.start is not None and entry.start.value:
            mapping[f"education.{index}.start"] = entry.start.value
            updates["start"] = DateValue(value=None, precision=DatePrecision.UNKNOWN)

        redacted.append(entry.model_copy(deep=True, update=updates) if updates else entry)

    return tuple(redacted)


def _earliest_role_year(resume: CanonicalResume) -> int | None:
    """Return the earliest year found in experience or project start/end dates.

    Education dates are deliberately excluded so that the graduation interval is
    computed relative to other career dates, not to itself (TRD §11.1).
    """
    dated_entries: list[ExperienceEntry | ProjectEntry] = [
        *resume.experience,
        *resume.projects,
    ]
    years = [
        _extract_year(date.value)
        for entry in dated_entries
        for date in (entry.start, entry.end)
        if date is not None and date.value
    ]
    present = [year for year in years if year is not None]
    if not present:
        return None
    return min(present)


def _graduation_interval(grad: DateValue, reference_year: int | None) -> str | None:
    """Return the interval between the graduation date and the first role
    start date as a string, e.g. '4 years before first role'.

    This preserves the experiential relationship without revealing the
    absolute graduation year (TRD §11.1).
    """
    if not grad.value or reference_year is None:
        return None

    grad_year = _extract_year(grad.value)
    if grad_year is None:
        return None

    return f"{reference_year - grad_year} years before first role"


def _extract_year(value: str) -> int | None:
    """Extract a four-digit year from a date string."""
    match = re.search(r"(19|20)\d{2}", value)
    if match:
        return int(match.group(0))
    return None


def _redact_experience(
    entries: tuple[ExperienceEntry, ...], mapping: ReidentificationMap
) -> tuple[ExperienceEntry, ...]:
    """Redact location details from experience entries."""
    redacted: list[ExperienceEntry] = []
    for index, entry in enumerate(entries):
        if entry.location is None:
            redacted.append(entry)
            continue
        redacted_location = _redact_location(
            entry.location, mapping, f"experience.{index}.location"
        )
        redacted.append(entry.model_copy(deep=True, update={"location": redacted_location}))
    return tuple(redacted)


def _redact_projects(
    entries: tuple[ProjectEntry, ...], mapping: ReidentificationMap
) -> tuple[ProjectEntry, ...]:
    """Redact location details from project entries."""
    redacted: list[ProjectEntry] = []
    for index, entry in enumerate(entries):
        if entry.location is None:
            redacted.append(entry)
            continue
        redacted_location = _redact_location(entry.location, mapping, f"projects.{index}.location")
        redacted.append(entry.model_copy(deep=True, update={"location": redacted_location}))
    return tuple(redacted)


def _redact_summary(
    summary: dict[str, object | None], mapping: ReidentificationMap
) -> dict[str, object | None]:
    """Redact known identity keys from the summary dict."""
    identity_keys = {
        "name",
        "full_name",
        "email",
        "emails",
        "phone",
        "phones",
        "dob",
        "date_of_birth",
        "gender",
        "nationality",
        "citizenship",
        "marital_status",
        "religion",
        "affiliations",
        "photo",
    }
    redacted: dict[str, object | None] = {}
    for key, value in summary.items():
        if key.lower() in identity_keys and value is not None:
            mapping[f"summary.{key}"] = str(value)
            redacted[key] = _REDACTED if isinstance(value, str) else None
        else:
            redacted[key] = value
    return redacted
