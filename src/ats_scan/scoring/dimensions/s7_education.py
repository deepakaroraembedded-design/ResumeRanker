from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume, Certification
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension

_DEGREE_ORDINALS: dict[str, int] = {
    "high_school": 1,
    "high school": 1,
    "ged": 1,
    "associate": 2,
    "associates": 2,
    "bachelor": 3,
    "bachelors": 3,
    "undergraduate": 3,
    "bs": 3,
    "ba": 3,
    "bsc": 3,
    "b.sc": 3,
    "btech": 3,
    "b.tech": 3,
    "be": 3,
    "b.e": 3,
    "bca": 3,
    "b.c.a": 3,
    "master": 4,
    "masters": 4,
    "mba": 4,
    "mca": 4,
    "m.sc": 4,
    "msc": 4,
    "ms": 4,
    "m.tech": 4,
    "mtech": 4,
    "doctorate": 5,
    "phd": 5,
    "ph.d": 5,
    "doctoral": 5,
}


@dimension
class S7Education:
    """Education and certifications (TRD §5.3.7)."""

    id: ClassVar[str] = "S7"
    name: ClassVar[str] = "Education and certifications"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.7 — Education and certifications.

        S7 = 100 * clip(0.6 * edu + 0.4 * cert, 0, 1). Institution prestige is
        deliberately not used. Certifications are neutral (1.0) when the JobSpec
        names none. Expired certs count at 0.40; in-progress certs count at 0.50.
        """
        now = date.fromisoformat(ctx.now)
        edu = _education_component(resume, spec, ctx)
        cert = _certification_component(resume, spec, now)
        raw = 0.6 * edu + 0.4 * cert
        value = max(0.0, min(100.0, 100.0 * raw))

        return SubScore(
            dimension=self.id,
            value=round(value, 2),
            evidence=(),
            detail={"edu": round(edu, 4), "cert": round(cert, 4)},
        )


def _education_component(resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> float:
    """Return the TRD §5.3.7 education component in [0, 1]."""
    if spec.education is None:
        return 1.0

    requirement = spec.education
    required_level = _degree_ordinal(requirement.min_level)
    if required_level == 0:
        return 1.0

    candidate_level = max(
        (_degree_ordinal(entry.degree_level) for entry in resume.education),
        default=0,
    )
    candidate_fields = {
        (entry.field or "").lower().strip() for entry in resume.education if entry.field
    }
    accepted_fields = {field.lower().strip() for field in requirement.fields}
    has_field = bool(candidate_fields & accepted_fields) if accepted_fields else True
    adjacent_field = bool(candidate_fields) and not has_field

    if candidate_level >= required_level and has_field:
        return 1.0
    if candidate_level >= required_level and adjacent_field:
        return 0.80

    if (
        candidate_level == required_level - 1
        and requirement.equivalent_experience_allowed
        and _relevant_years(resume, spec)
        >= (spec.experience.min_years + 2 if spec.experience else 2)
    ):
        return 0.70

    return max(0.20, min(1.0, candidate_level / required_level))


def _relevant_years(resume: CanonicalResume, spec: JobSpec) -> float:
    """Best-effort relevant years for the equivalent-experience fallback."""
    if resume.timeline and resume.timeline.total_months_covered is not None:
        return resume.timeline.total_months_covered / 12.0
    if spec.experience and spec.experience.min_years:
        return float(spec.experience.min_years)
    return 0.0


def _certification_component(resume: CanonicalResume, spec: JobSpec, now: date) -> float:
    """Return the TRD §5.3.7 certification component in [0, 1]."""
    required = tuple(spec.certifications)
    if not required:
        return 1.0

    total_weight = 0.0
    matched_weight = 0.0
    for req in required:
        name = _cert_name(req)
        raw_weight = req.get("weight", 1) if isinstance(req, dict) else 1
        weight = float(raw_weight) if isinstance(raw_weight, (int, float)) else 1.0
        total_weight += weight
        match = _match_certification(name, resume.certifications, now)
        matched_weight += weight * match

    if total_weight == 0.0:
        return 1.0
    return max(0.0, min(1.0, matched_weight / total_weight))


def _cert_name(req: dict[str, object]) -> str:
    """Extract the canonical name from a JobSpec certification entry."""
    for key in ("canonical", "name", "title"):
        value = req.get(key)
        if isinstance(value, str):
            return value.lower().strip()
    return ""


def _match_certification(target: str, certs: tuple[Certification, ...], now: date) -> float:
    """Return the best certification match factor for a target credential."""
    if not target or not certs:
        return 0.0

    best = 0.0
    for cert in certs:
        name = (cert.canonical or cert.name or "").lower().strip()
        if not name or target != name:
            continue

        factor = 1.0
        if cert.expires:
            expiry = _parse_date(cert.expires)
            if expiry is not None and expiry < now:
                factor = 0.40
        if cert.status:
            status = cert.status.lower().strip()
            if status in ("in-progress", "candidate", "pending"):
                factor = 0.50
        if factor > best:
            best = factor
    return best


def _degree_ordinal(level: str | None) -> int:
    """Map a degree-level string to an ordinal."""
    if level is None:
        return 0
    normalized = level.lower().strip().replace(".", "").replace("'", "")
    return _DEGREE_ORDINALS.get(normalized, 0)


def _parse_date(raw: str) -> date | None:
    """Parse a date string for certification expiry/status checks."""
    if len(raw) == 7:  # YYYY-MM
        try:
            return datetime.strptime(raw, "%Y-%m").date()
        except ValueError:
            return None
    if len(raw) == 4:  # YYYY
        try:
            return date(int(raw), 1, 1)
        except ValueError:
            return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None
