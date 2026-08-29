from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension


@dimension
class S5Title:
    """Role and title alignment (TRD §5.3.5)."""

    id: ClassVar[str] = "S5"
    name: ClassVar[str] = "Role and title alignment"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.5 — Role and title alignment."""
        raise NotImplementedError("implemented by component agent")
