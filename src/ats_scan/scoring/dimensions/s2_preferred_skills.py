from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension


@dimension
class S2PreferredSkills:
    """Preferred skills coverage (TRD §5.3.2)."""

    id: ClassVar[str] = "S2"
    name: ClassVar[str] = "Preferred skills coverage"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.2 — Preferred skills coverage."""
        raise NotImplementedError("implemented by component agent")
