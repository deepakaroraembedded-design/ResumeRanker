#!/usr/bin/env python3
"""Generate scoring dimension stubs with NotImplementedError in score methods."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DIMS = [
    ("s1_required_skills", "S1", "S1RequiredSkills", "Required skills coverage"),
    ("s2_preferred_skills", "S2", "S2PreferredSkills", "Preferred skills coverage"),
    ("s3_semantic", "S3", "S3Semantic", "Semantic relevance"),
    ("s4_experience", "S4", "S4Experience", "Relevant experience depth"),
    ("s5_title", "S5", "S5Title", "Role and title alignment"),
    ("s6_domain", "S6", "S6Domain", "Domain and industry match"),
    ("s7_education", "S7", "S7Education", "Education and certifications"),
    ("s8_skill_recency", "S8", "S8SkillRecency", "Skill recency"),
    ("s9_trajectory", "S9", "S9Trajectory", "Career trajectory and stability"),
    ("s10_parseability", "S10", "S10Parseability", "Resume parseability"),
]

TEMPLATE = '''from __future__ import annotations

from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension


@dimension
class {class_name}:
    """{name} (TRD §5.3.{idx})."""

    id: ClassVar[str] = "{id}"
    name: ClassVar[str] = "{name}"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.{idx} — {name}."""
        raise NotImplementedError("implemented by component agent")
'''


def main() -> None:
    for idx, (module, dim_id, class_name, name) in enumerate(DIMS, start=1):
        path = ROOT / f"src/ats_scan/scoring/dimensions/{module}.py"
        path.write_text(
            TEMPLATE.format(idx=idx, id=dim_id, class_name=class_name, name=name),
            encoding="utf-8",
        )
    print(f"Generated {len(DIMS)} dimension stubs.")


if __name__ == "__main__":
    main()
