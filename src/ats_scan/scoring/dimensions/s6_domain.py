from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension


@dimension
class S6Domain:
    """Domain and industry match (TRD §5.3.6)."""

    id: ClassVar[str] = "S6"
    name: ClassVar[str] = "Domain and industry match"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.6 — Domain and industry match."""
        raise NotImplementedError("implemented by component agent")
