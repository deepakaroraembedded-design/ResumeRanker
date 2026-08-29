from __future__ import annotations

from tests.qa.oracle.aggregate import aggregate
from tests.qa.oracle.bands import band
from tests.qa.oracle.confidence import confidence
from tests.qa.oracle.s1 import s1_required_skills
from tests.qa.oracle.s2 import s2_preferred_skills
from tests.qa.oracle.s3 import s3_semantic
from tests.qa.oracle.s4 import s4_experience
from tests.qa.oracle.s5 import s5_title
from tests.qa.oracle.s6 import s6_domain
from tests.qa.oracle.s7 import s7_education
from tests.qa.oracle.s8 import s8_skill_recency
from tests.qa.oracle.s9 import s9_trajectory
from tests.qa.oracle.s10 import s10_parseability
from tests.qa.oracle.tiebreak import rank_candidates

"""Blind-derived reference oracle for the ATS-Scan scoring model."""

__all__ = [
    "aggregate",
    "band",
    "confidence",
    "rank_candidates",
    "s1_required_skills",
    "s2_preferred_skills",
    "s3_semantic",
    "s4_experience",
    "s5_title",
    "s6_domain",
    "s7_education",
    "s8_skill_recency",
    "s9_trajectory",
    "s10_parseability",
]
