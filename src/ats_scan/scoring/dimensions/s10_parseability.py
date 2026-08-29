from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume, DatePrecision
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension


@dimension
class S10Parseability:
    """Resume parseability (TRD §5.3.10)."""

    id: ClassVar[str] = "S10"
    name: ClassVar[str] = "Resume parseability"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.10 — Resume parseability.

        Start at 100 and apply fixed deductions: OCR required -40, multi-column
        layout -15, missing critical sections up to -30, unparseable dates in >25%
        of roles -15, missing contact block -10. Floor at 0. S10 is a document
        quality signal and is never a knockout.
        """
        deductions = 0
        extraction = resume.extraction
        method = (extraction.method or "").lower() if extraction else ""
        if method in ("ocr", "tesseract"):
            deductions += 40

        columns = extraction.columns_detected if extraction else None
        if columns and columns > 1:
            deductions += 15

        missing_sections = 0
        if not resume.experience:
            missing_sections += 1
        if not resume.skills:
            missing_sections += 1
        if not resume.education:
            missing_sections += 1
        deductions += min(2, missing_sections) * 15

        unparseable_roles = 0
        total_roles = 0
        for role in resume.experience:
            total_roles += 1
            start_missing = role.start is None or _is_unparseable(role.start)
            end_missing = role.end is None or _is_unparseable(role.end)
            if start_missing or end_missing:
                unparseable_roles += 1
        if total_roles > 0 and unparseable_roles / total_roles > 0.25:
            deductions += 15

        # Contact block deduction is ignored in blind mode; without a fairness
        # flag in ScoringContext we conservatively skip it to avoid penalising
        # redacted resumes.

        value = max(0.0, 100.0 - deductions)
        return SubScore(
            dimension=self.id,
            value=round(value, 2),
            evidence=(),
            detail={"deductions": deductions, "parse_completeness": resume.parse_completeness},
        )


def _is_unparseable(value: object) -> bool:
    """Return True when a DateValue cannot be resolved to a date."""
    if value is None:
        return True
    precision = getattr(value, "precision", None)
    if precision == DatePrecision.UNKNOWN:
        return True
    if precision == DatePrecision.PRESENT:
        return False
    raw = getattr(value, "value", None)
    return raw is None
