from __future__ import annotations

from typing import Any

import pytest
from tests.qa.strategies import skill_case

from ats_scan.scoring.dimensions.s1_required_skills import S1RequiredSkills
from ats_scan.scoring.dimensions.s2_preferred_skills import S2PreferredSkills
from ats_scan.scoring.dimensions.s3_semantic import S3Semantic
from ats_scan.scoring.dimensions.s4_experience import S4Experience
from ats_scan.scoring.dimensions.s5_title import S5Title
from ats_scan.scoring.dimensions.s6_domain import S6Domain
from ats_scan.scoring.dimensions.s7_education import S7Education
from ats_scan.scoring.dimensions.s8_skill_recency import S8SkillRecency
from ats_scan.scoring.dimensions.s9_trajectory import S9Trajectory
from ats_scan.scoring.dimensions.s10_parseability import S10Parseability

DIMENSIONS: dict[str, Any] = {
    "S1": S1RequiredSkills,
    "S2": S2PreferredSkills,
    "S3": S3Semantic,
    "S4": S4Experience,
    "S5": S5Title,
    "S6": S6Domain,
    "S7": S7Education,
    "S8": S8SkillRecency,
    "S9": S9Trajectory,
    "S10": S10Parseability,
}


@pytest.mark.slow
@pytest.mark.parametrize("dim", list(DIMENSIONS))
def test_dimension_agrees_with_oracle(dim: str) -> None:
    """Differential oracle check for a single scoring dimension."""
    cls = DIMENSIONS[dim]
    resume, spec, ctx, oracle_inputs = skill_case()

    try:
        sub = cls().score(resume, spec, ctx)
    except NotImplementedError:
        pytest.skip(f"{dim} implementation is not available yet")

    if dim not in oracle_inputs:
        pytest.skip(f"oracle case for {dim} is not yet defined")

    expected = oracle_inputs[dim]
    assert sub.value == pytest.approx(expected, abs=1e-6), dim
