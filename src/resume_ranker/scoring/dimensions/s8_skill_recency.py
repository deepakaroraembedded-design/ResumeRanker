from __future__ import annotations

from typing import ClassVar, cast

from resume_ranker.models.jobspec import JobSpec
from resume_ranker.models.resume import CanonicalResume
from resume_ranker.models.run import ScoringContext
from resume_ranker.models.scoring import Evidence, SubScore
from resume_ranker.protocols import OntologyIndex
from resume_ranker.scoring.evidence import parse_iso_date, recency_for_skill
from resume_ranker.scoring.registry import dimension


@dimension
class S8SkillRecency:
    """Skill recency (TRD §5.3.8)."""

    id: ClassVar[str] = "S8"
    name: ClassVar[str] = "Skill recency"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.8 — S8 = 100 × mean of f_recency over the three highest-weighted required skills.

        Ties are broken by canonical name for deterministic ordering.
        A skill with no evidence contributes 0 to the mean.
        """
        required = spec.required_skills
        if not required:
            return SubScore(dimension=self.id, value=None, evidence=())

        ontology = cast(OntologyIndex, ctx.ontology)
        now = parse_iso_date(ctx.now)
        recency_cfg = ctx.config.recency

        top = sorted(required, key=lambda s: (-s.weight, s.canonical))[:3]

        evidence_out: list[Evidence] = []
        total = 0.0
        for skill in top:
            rec, best_ev = recency_for_skill(
                resume, skill.canonical, now, recency_cfg, ontology, ctx
            )
            total += rec
            if best_ev is not None:
                evidence_out.append(
                    Evidence(span=best_ev.span, quote=best_ev.quote, page=None, source="resume")
                )

        mean = total / len(top)
        return SubScore(
            dimension=self.id,
            value=100.0 * mean,
            evidence=tuple(evidence_out),
            detail={"top_skills": [s.canonical for s in top]},
        )
