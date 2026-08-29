from __future__ import annotations

from datetime import date
from typing import Any

from tests.fakes import FakeEmbeddingClient, FakeOntology, FakeTitleTaxonomy

from ats_scan.models.config import ScoringConfig
from ats_scan.models.jobspec import JobSpec, PreferredSkill, RequiredSkill
from ats_scan.models.resume import CanonicalResume, SkillMention
from ats_scan.models.run import ScoringContext


def scoring_context(now: str = "2026-08-29") -> ScoringContext:
    """Return a deterministic context usable by the scoring engine."""
    return ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=FakeEmbeddingClient(),
        llm=None,
        config=ScoringConfig(),
        now=now,
    )


def skill_case() -> tuple[CanonicalResume, JobSpec, ScoringContext, dict[str, Any]]:
    """Return a minimal skill-coverage case and pre-resolved oracle inputs."""
    resume = CanonicalResume(
        candidate_id="c_diff",
        skills=(
            SkillMention(raw="Python", canonical="python", last_used="2026-08"),
            SkillMention(raw="Spark", canonical="apache-spark", last_used="2026-08"),
        ),
    )
    spec = JobSpec(
        job_id="jd_diff",
        title="Test role",
        required_skills=(
            RequiredSkill(canonical="python", weight=5),
            RequiredSkill(canonical="apache-spark", weight=5),
            RequiredSkill(canonical="dbt", weight=2),
        ),
        preferred_skills=(PreferredSkill(canonical="kafka", weight=3),),
    )
    evidence = {
        "python": [
            {"route": "exact", "proficiency": "listed_corroborated", "last_used": "2026-08"}
        ],
        "apache-spark": [
            {"route": "exact", "proficiency": "listed_corroborated", "last_used": "2026-08"}
        ],
        "kafka": [{"route": "exact", "proficiency": "listed_only", "last_used": "2026-08"}],
    }
    cfg = scoring_context().config.model_dump()
    now_date = date.fromisoformat("2026-08-29")
    oracle_inputs = {
        "S1": oracle_value(
            "s1",
            [r.model_dump() for r in spec.required_skills],
            evidence,
            cfg,
            now_date,
        ),
        "S2": oracle_value(
            "s2",
            [p.model_dump() for p in spec.preferred_skills],
            evidence,
            cfg,
            now_date,
        ),
    }
    return resume, spec, scoring_context(), oracle_inputs


def oracle_value(
    dim: str,
    skills: list[dict[str, Any]],
    evidence: dict[str, list[dict[str, Any]]],
    cfg: dict[str, Any],
    now: date,
) -> float:
    """Compute the oracle value for a skill dimension."""
    from tests.qa import oracle

    if dim == "s1":
        return oracle.s1_required_skills(skills, evidence, cfg, now)
    if dim == "s2":
        return oracle.s2_preferred_skills(skills, evidence, cfg, now)
    msg = f"unknown skill dimension: {dim}"
    raise ValueError(msg)
