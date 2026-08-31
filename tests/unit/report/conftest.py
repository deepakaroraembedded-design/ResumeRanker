from __future__ import annotations

import pytest

from resume_ranker.models.common import Diagnostic
from resume_ranker.models.jobspec import JobSpec, RequiredSkill
from resume_ranker.models.resume import CanonicalResume, Identity, SkillMention, SourceDocument
from resume_ranker.models.run import RunManifest, RunResult
from resume_ranker.models.scoring import (
    Band,
    Evidence,
    GapDetail,
    KnockoutResult,
    MatchDetail,
    Provenance,
    ScoreCard,
    SubScore,
)


@pytest.fixture
def scorecard_one() -> ScoreCard:
    """A single strongly-matched candidate used across report tests."""
    return ScoreCard(
        candidate_id="c_abc123",
        job_id="jd_001",
        run_id="run_001",
        eligible=True,
        selected=True,
        rank=1,
        composite=87.06,
        base_score=87.06,
        band=Band.STRONG,
        confidence=0.91,
        sub_scores={
            "S1": SubScore(
                dimension="S1",
                value=88.40,
                evidence=(Evidence(span=(10, 20), quote="Python expert", page=1),),
            ),
            "S2": SubScore(dimension="S2", value=60.00),
            "S3": SubScore(dimension="S3", value=79.10),
            "S4": SubScore(dimension="S4", value=92.00, detail={"relevant_years": 7.20}),
            "S5": SubScore(dimension="S5", value=100.00),
            "S6": SubScore(dimension="S6", value=100.00),
            "S7": SubScore(dimension="S7", value=84.00),
            "S8": SubScore(dimension="S8", value=96.30),
            "S9": SubScore(dimension="S9", value=100.00),
            "S10": SubScore(dimension="S10", value=100.00),
        },
        matched=(
            MatchDetail(
                criterion="python",
                weight=5,
                match=1.00,
                evidence=(Evidence(span=(10, 20), quote="Python expert", page=1),),
            ),
        ),
        gaps=(GapDetail(criterion="dbt", weight=2, searched=("dbt", "data build tool")),),
        explanation="Strong match with deep Python experience and relevant data engineering background.",
        provenance=Provenance(
            config_sha256="sha-config",
            ontology_version="2026.07",
            code_version="1.0.0",
            models={"llm": None, "embed": None},
            scored_at="2026-08-29T14:07:44Z",
        ),
    )


@pytest.fixture
def scorecard_two() -> ScoreCard:
    """A second candidate with flags and a lower score for review-queue tests."""
    return ScoreCard(
        candidate_id="c_def456",
        job_id="jd_001",
        run_id="run_001",
        eligible=False,
        selected=False,
        rank=2,
        composite=42.50,
        base_score=42.50,
        band=Band.WEAK,
        confidence=0.55,
        sub_scores={
            "S1": SubScore(dimension="S1", value=45.00),
            "S2": SubScore(dimension="S2", value=30.00),
            "S3": SubScore(dimension="S3", value=50.00),
            "S4": SubScore(dimension="S4", value=40.00),
            "S5": SubScore(dimension="S5", value=60.00),
            "S6": SubScore(dimension="S6", value=20.00),
            "S7": SubScore(dimension="S7", value=70.00),
            "S8": SubScore(dimension="S8", value=80.00),
            "S9": SubScore(dimension="S9", value=90.00),
            "S10": SubScore(dimension="S10", value=95.00),
        },
        knockout_results=(KnockoutResult(id="KO_WORK_AUTH", verdict="FAIL"),),
        gaps=(GapDetail(criterion="apache-spark", weight=5),),
        flags=("LOW_CONFIDENCE",),
        reason_codes=("KO_WORK_AUTH",),
        explanation="Weak match; missing key requirements and low confidence.",
    )


@pytest.fixture
def sample_run(scorecard_one: ScoreCard, scorecard_two: ScoreCard) -> RunResult:
    """A fixed RunResult with two candidates and one diagnostic error."""
    resume_one = CanonicalResume(
        candidate_id="c_abc123",
        source=SourceDocument(
            path="resumes/abc123.pdf",
            content_sha256="abc123",
            bytes=1234,
            mtime="2026-08-29T00:00:00Z",
            media_type="application/pdf",
        ),
        identity=Identity(full_name="Alice Smith"),
        skills=(
            SkillMention(raw="Python", canonical="python", sections=("skills",), mentions=3),
            SkillMention(raw="MysterySkill", canonical=None, sections=("skills",), mentions=1),
        ),
    )
    resume_two = CanonicalResume(
        candidate_id="c_def456",
        source=SourceDocument(
            path="resumes/def456.pdf",
            content_sha256="def456",
            bytes=2345,
            mtime="2026-08-29T00:00:00Z",
            media_type="application/pdf",
        ),
        identity=Identity(full_name="Bob Jones"),
    )

    return RunResult(
        manifest=RunManifest(
            run_id="run_001",
            config_hash="sha-config",
            ontology_version="2026.07",
            code_version="1.0.0",
            started_at="2026-08-29T14:00:00Z",
            calibration_anchors={"p10": 0.30, "p90": 0.75},
        ),
        scorecards=(scorecard_one, scorecard_two),
        jobspec=JobSpec(
            job_id="jd_001",
            title="Senior Data Engineer",
            required_skills=(RequiredSkill(canonical="python", weight=5),),
        ),
        resumes={"c_abc123": resume_one, "c_def456": resume_two},
        diagnostics=(
            Diagnostic(stage="S2", code="EXT_CORRUPT", message="Could not read pages 3-4"),
        ),
    )


@pytest.fixture
def blind_run(scorecard_one: ScoreCard) -> RunResult:
    """A run in blind mode: the candidate name is redacted."""
    resume = CanonicalResume(
        candidate_id="c_abc123",
        source=SourceDocument(
            path="resumes/abc123.pdf",
            content_sha256="abc123",
            bytes=1234,
            mtime="2026-08-29T00:00:00Z",
            media_type="application/pdf",
        ),
        identity=Identity(full_name=None),
    )
    return RunResult(
        manifest=RunManifest(
            run_id="run_001",
            config_hash="sha-config",
            ontology_version="2026.07",
            code_version="1.0.0",
            started_at="2026-08-29T14:00:00Z",
        ),
        scorecards=(scorecard_one,),
        jobspec=JobSpec(job_id="jd_001", title="Senior Data Engineer"),
        resumes={"c_abc123": resume},
    )
