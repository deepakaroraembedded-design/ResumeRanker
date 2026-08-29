from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension


@dimension
class S7Education:
    """Education and certifications (TRD §5.3.7)."""

    id: ClassVar[str] = "S7"
    name: ClassVar[str] = "Education and certifications"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.7 — Education and certifications."""
        raise NotImplementedError("implemented by component agent")
