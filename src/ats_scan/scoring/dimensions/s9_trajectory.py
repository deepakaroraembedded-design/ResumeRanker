from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension


@dimension
class S9Trajectory:
    """Career trajectory and stability (TRD §5.3.9)."""

    id: ClassVar[str] = "S9"
    name: ClassVar[str] = "Career trajectory and stability"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.9 — Career trajectory and stability."""
        raise NotImplementedError("implemented by component agent")
