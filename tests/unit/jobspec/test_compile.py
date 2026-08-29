from __future__ import annotations

from pathlib import Path

import pytest

from ats_scan.jobspec import JobSpecCompiler
from ats_scan.models.jobspec import (
    ExperienceRequirement,
    PreferredSkill,
    RequiredSkill,
)
from ats_scan.models.run import RunContext
from ats_scan.protocols import JobSpecCompiler as JobSpecCompilerProtocol

JD_FIXTURES = [
    (
        "jd_000_software_engineering.md",
        "Senior Software Engineer",
        ["javascript", "aws", "sql", "kubernetes", "java"],
        ["python", "react"],
        6,
    ),
    (
        "jd_001_qa_automation.md",
        "Senior QA Automation",
        ["playwright", "jenkins", "git", "python", "pytest"],
        ["selenium", "cypress"],
        4,
    ),
    (
        "jd_002_data_engineering.md",
        "Senior Data Engineer",
        ["spark", "aws", "sql", "dbt", "terraform"],
        ["python", "airflow"],
        4,
    ),
    (
        "jd_003_devops.md",
        "Senior DevOps",
        ["git", "kubernetes", "aws", "python", "terraform"],
        ["bash", "docker"],
        3,
    ),
    (
        "jd_004_product_management.md",
        "Senior Product Management",
        ["jira", "scrum", "confluence", "agile", "python"],
        ["sql", "tableau"],
        5,
    ),
]


@pytest.mark.parametrize(
    "filename,title,required,preferred,min_years",
    JD_FIXTURES,
)
def test_compile_fixture_jd(
    compiler: JobSpecCompiler,
    run_context: RunContext,
    read_corpus_jd,
    filename: str,
    title: str,
    required: list[str],
    preferred: list[str],
    min_years: int,
) -> None:
    """Snapshot-style acceptance over the five Wave-0 JD fixtures."""
    source = read_corpus_jd(filename)
    result = compiler.compile(source, run_context)
    assert result.ok, result.diagnostics
    spec = result.value
    assert spec.title == title
    assert spec.target_seniority == "senior"
    assert spec.compiled_by == "heuristic:rule"
    assert [s.canonical for s in spec.required_skills] == required
    assert [s.weight for s in spec.required_skills] == [3] * len(required)
    assert [s.canonical for s in spec.preferred_skills] == preferred
    assert [s.weight for s in spec.preferred_skills] == [2] * len(preferred)
    assert spec.experience == ExperienceRequirement(
        min_years=min_years, target_years=min_years + 3, count_internships=False
    )


def test_satisfies_protocol(compiler: JobSpecCompiler) -> None:
    """The default compiler satisfies the JobSpecCompiler protocol."""
    assert isinstance(compiler, JobSpecCompilerProtocol)


def test_compile_yaml_bypasses_llm(compiler: JobSpecCompiler, run_context: RunContext) -> None:
    """FR-402: hand-authored YAML bypasses the free-text parser."""
    source = """
job_id: jd_manual_yaml
title: Manual YAML Job
required_skills:
  - canonical: python
    weight: 5
    knockout: false
preferred_skills:
  - canonical: sql
    weight: 2
experience:
  min_years: 3
  target_years: 5
  count_internships: false
"""
    result = compiler.compile(source, run_context)
    assert result.ok, result.diagnostics
    spec = result.value
    assert spec.job_id == "jd_manual_yaml"
    assert spec.title == "Manual YAML Job"
    assert spec.required_skills == (RequiredSkill(canonical="python", weight=5),)
    assert spec.preferred_skills == (PreferredSkill(canonical="sql", weight=2),)


def test_compile_json_bypasses_llm(compiler: JobSpecCompiler, run_context: RunContext) -> None:
    """FR-402: hand-authored JSON also bypasses the free-text parser."""
    source = (
        '{"job_id": "jd_json", "title": "JSON Job", '
        '"required_skills": [{"canonical": "go", "weight": 4}], '
        '"preferred_skills": []}'
    )
    result = compiler.compile(source, run_context)
    assert result.ok, result.diagnostics
    assert result.value.job_id == "jd_json"
    assert result.value.title == "JSON Job"


def test_compile_invalid_yaml_is_fatal(compiler: JobSpecCompiler, run_context: RunContext) -> None:
    """A hand-authored JobSpec that fails validation is a fatal error."""
    source = """
job_id: bad
title: Bad
required_skills: not_a_list
"""
    result = compiler.compile(source, run_context)
    assert not result.ok
    assert any(d.fatal for d in result.diagnostics)


def test_compile_empty_source_is_fatal(compiler: JobSpecCompiler, run_context: RunContext) -> None:
    """Empty JD source is a fatal compilation error."""
    result = compiler.compile("", run_context)
    assert not result.ok
    assert any(d.fatal and d.code == "JD_EMPTY" for d in result.diagnostics)


def test_compile_whitespace_source_is_fatal(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    result = compiler.compile("   \n\t  \n", run_context)
    assert not result.ok
    assert any(d.fatal for d in result.diagnostics)


def test_ambiguous_requirements_default_to_weighted(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """FR-404: ambiguous requirements are weighted, never knockouts."""
    source = "Role\n\nRequired:\n- Some experience with Rust\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    assert result.value.knockouts == ()
    assert any(s.canonical == "rust" for s in result.value.required_skills)


def test_importance_weights_overridable(run_context: RunContext) -> None:
    """FR-405: weight phrases can be overridden via configuration."""
    custom_phrases = (("crucial", 5), ("helpful", 2))
    compiler = JobSpecCompiler(weight_phrases=custom_phrases)
    source = "Role\n\nRequired:\n- crucial Python\n- helpful Rust\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    weights = {s.canonical: s.weight for s in result.value.required_skills}
    assert weights == {"python": 5, "rust": 2}


def test_importance_weights_from_language(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """FR-405: required-skills weights are derived from requirement language."""
    source = (
        "Role\n\nRequired:\n"
        "- must have Python\n"
        "- strong Java\n"
        "- experience with Go\n"
        "- exposure to Kotlin\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    weights = {s.canonical: s.weight for s in result.value.required_skills}
    assert weights == {
        "python": 5,
        "java": 4,
        "go": 3,
        "kotlin": 2,
    }


def test_warning_above_required_skill_limit(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """FR-406: warn when more than 12 required skills are compiled."""
    skills = "\n".join(f"- skill{i}" for i in range(14))
    source = f"Role\n\nRequired:\n{skills}\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    assert any("limit 12" in w for w in result.value.warnings)


def test_protected_proxy_language_flagged(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """FR-407: protected-proxy language is flagged, not silently accepted."""
    source = (
        "Role\n\nRequired:\n- Python\n\nWe are looking for a digital native with no career gaps."
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    warnings = result.value.warnings
    assert any("digital native" in w for w in warnings)
    assert any("career gaps" in w for w in warnings)


def test_proxy_knockout_requires_acknowledgement(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """FR-407: a hand-authored knockout with proxy language requires acknowledgement."""
    source = """
job_id: jd_proxy
title: Proxy Job
knockouts:
  - id: KO_AGE
    rule: recent graduate only
    evidence_required: true
"""
    result = compiler.compile(source, run_context)
    assert not result.ok
    assert any("recent graduate" in d.message for d in result.diagnostics)


def test_proxy_knockout_allowed_when_acknowledged(run_context: RunContext) -> None:
    source = """
job_id: jd_proxy
title: Proxy Job
knockouts:
  - id: KO_AGE
    rule: recent graduate only
    evidence_required: true
"""
    compiler = JobSpecCompiler(acknowledged_proxies=("recent graduate",))
    result = compiler.compile(source, run_context)
    assert result.ok, result.diagnostics


def test_review_file_written(
    compiler: JobSpecCompiler, run_context: RunContext, output_dir: Path
) -> None:
    """FR-403: the compiled JobSpec is written to the output directory."""
    source = "Role\n\nRequired:\n- Python\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    assert (output_dir / "jobspec.yaml").exists()


def test_review_mode_writes_pending_sidecar(run_context: RunContext, output_dir: Path) -> None:
    """FR-403: review mode writes a pending sidecar alongside the JobSpec."""
    compiler = JobSpecCompiler(review_mode=True)
    source = "Role\n\nRequired:\n- Python\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    assert (output_dir / "jobspec.yaml").exists()
    assert (output_dir / "jobspec.review.yaml").exists()


def test_knockout_rules_from_sections(compiler: JobSpecCompiler, run_context: RunContext) -> None:
    """FR-401: explicit knockout sections are turned into KnockoutRule objects."""
    source = (
        "Role\n\nRequired:\n- Python\n\n"
        "Work Authorization:\n- Must be authorized to work in the US\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    assert len(result.value.knockouts) == 1
    assert "authorized to work" in result.value.knockouts[0].rule.lower()
