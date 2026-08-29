from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension


@dimension
class S3Semantic:
    """Semantic relevance (TRD §5.3.3)."""

    id: ClassVar[str] = "S3"
    name: ClassVar[str] = "Semantic relevance"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.3 — Semantic relevance."""
        raise NotImplementedError("implemented by component agent")
