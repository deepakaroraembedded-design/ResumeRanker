from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.evidence import score_skill_coverage
from ats_scan.scoring.registry import dimension


@dimension
class S1RequiredSkills:
    """Required skills coverage (TRD §5.3.1)."""

    id: ClassVar[str] = "S1"
    name: ClassVar[str] = "Required skills coverage"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.1 — S1 = 100 × Σ(w_i·m_i) / Σ(w_i) over evidenced skills."""
        required = spec.required_skills
        if not required:
            return SubScore(dimension=self.id, value=100.0, evidence=())

        value, evidence, matches, gaps = score_skill_coverage(resume, required, ctx)
        return SubScore(
            dimension=self.id,
            value=value,
            evidence=evidence,
            detail={
                "matches": matches,
                "gaps": gaps,
                "gate": {"passed": len(matches), "total": len(required)},
            },
        )
