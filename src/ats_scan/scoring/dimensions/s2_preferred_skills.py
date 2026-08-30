from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.evidence import score_skill_coverage
from ats_scan.scoring.registry import dimension


@dimension
class S2PreferredSkills:
    """Preferred skills coverage (TRD §5.3.2)."""

    id: ClassVar[str] = "S2"
    name: ClassVar[str] = "Preferred skills coverage"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.2 — S2 = 100 × Σ(v_j·m_j) / Σ(v_j); returns None if no preferred skills."""
        preferred = spec.preferred_skills
        if not preferred:
            return SubScore(dimension=self.id, value=None, evidence=())

        value, evidence, matches, gaps = score_skill_coverage(resume, preferred, ctx)
        return SubScore(
            dimension=self.id,
            value=value,
            evidence=evidence,
            detail={
                "matches": matches,
                "gaps": gaps,
                "gate": {"passed": len(matches), "total": len(preferred)},
            },
        )
