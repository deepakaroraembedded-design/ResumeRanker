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
@pytest.mark.covers("FR-401")
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


@pytest.mark.covers("FR-401")
def test_satisfies_protocol(compiler: JobSpecCompiler) -> None:
    """The default compiler satisfies the JobSpecCompiler protocol."""
    assert isinstance(compiler, JobSpecCompilerProtocol)


@pytest.mark.covers("FR-402")
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


@pytest.mark.covers("FR-402")
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


@pytest.mark.covers("FR-402")
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


@pytest.mark.covers("FR-401")
def test_compile_empty_source_is_fatal(compiler: JobSpecCompiler, run_context: RunContext) -> None:
    """Empty JD source is a fatal compilation error."""
    result = compiler.compile("", run_context)
    assert not result.ok
    assert any(d.fatal and d.code == "JD_EMPTY" for d in result.diagnostics)


@pytest.mark.covers("FR-401")
def test_compile_whitespace_source_is_fatal(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    result = compiler.compile("   \n\t  \n", run_context)
    assert not result.ok
    assert any(d.fatal for d in result.diagnostics)


@pytest.mark.covers("FR-404")
def test_ambiguous_requirements_default_to_weighted(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """FR-404: ambiguous requirements are weighted, never knockouts."""
    source = "Role\n\nRequired:\n- Some experience with Rust\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    assert result.value.knockouts == ()
    assert any(s.canonical == "rust" for s in result.value.required_skills)


@pytest.mark.covers("FR-405")
def test_importance_weights_overridable(run_context: RunContext) -> None:
    """FR-405: weight phrases can be overridden via configuration."""
    custom_phrases = (("crucial", 5), ("helpful", 2))
    compiler = JobSpecCompiler(weight_phrases=custom_phrases)
    source = "Role\n\nRequired:\n- crucial Python\n- helpful Rust\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    weights = {s.canonical: s.weight for s in result.value.required_skills}
    assert weights == {"python": 5, "rust": 2}


@pytest.mark.covers("FR-405")
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


@pytest.mark.covers("FR-406")
def test_warning_above_required_skill_limit(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """FR-406: warn when more than 12 required skills are compiled."""
    skills = "\n".join(f"- skill{i}" for i in range(14))
    source = f"Role\n\nRequired:\n{skills}\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    assert any("limit 12" in w for w in result.value.warnings)


@pytest.mark.covers("FR-407")
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


@pytest.mark.covers("FR-407")
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


@pytest.mark.covers("FR-407")
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


@pytest.mark.covers("FR-403")
def test_review_file_written(
    compiler: JobSpecCompiler, run_context: RunContext, output_dir: Path
) -> None:
    """FR-403: the compiled JobSpec is written to the output directory."""
    source = "Role\n\nRequired:\n- Python\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    assert (output_dir / "jobspec.yaml").exists()


@pytest.mark.covers("FR-403")
def test_review_mode_writes_pending_sidecar(run_context: RunContext, output_dir: Path) -> None:
    """FR-403: review mode writes a pending sidecar alongside the JobSpec."""
    compiler = JobSpecCompiler(review_mode=True)
    source = "Role\n\nRequired:\n- Python\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    assert (output_dir / "jobspec.yaml").exists()
    assert (output_dir / "jobspec.review.yaml").exists()


@pytest.mark.covers("FR-401")
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


@pytest.mark.covers("FR-402")
def test_compile_structured_looks_like_yaml_but_not_dict(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """A YAML/JSON-looking source that is not a dict falls back to free-text parsing."""
    result = compiler.compile("- just a list\n- of items\n", run_context)
    assert result.ok, result.diagnostics


@pytest.mark.covers("FR-402")
def test_compile_structured_without_job_id_or_title(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """A YAML mapping without job_id or title falls back to free-text parsing."""
    result = compiler.compile("foo: bar\n", run_context)
    assert result.ok, result.diagnostics


@pytest.mark.covers("FR-402")
def test_compile_malformed_json_falls_back_to_free_text(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """Malformed JSON that looks structured falls back to free-text parsing."""
    result = compiler.compile('{"job_id": "bad", "title": "Bad"', run_context)
    assert result.ok, result.diagnostics


@pytest.mark.covers("FR-403")
def test_compile_jd_write_failure_on_read_only_dir(
    compiler: JobSpecCompiler, run_context: RunContext, tmp_path: Path
) -> None:
    """An OSError when writing the review JobSpec is surfaced as a fatal diagnostic."""
    read_only = tmp_path / "readonly"
    read_only.mkdir(mode=0o555)
    ctx = RunContext(run_id="test", output_dir=read_only)
    result = compiler.compile("Role\n\nRequired:\n- Python\n", ctx)
    assert not result.ok
    assert any(d.code == "JD_WRITE_FAILED" for d in result.diagnostics)


@pytest.mark.covers("FR-401")
def test_seniority_inference_junior(compiler: JobSpecCompiler, run_context: RunContext) -> None:
    result = compiler.compile("Junior Data Engineer\n\nRequired:\n- Python\n", run_context)
    assert result.ok
    assert result.value.target_seniority == "junior"


@pytest.mark.covers("FR-401")
def test_seniority_inference_lead(compiler: JobSpecCompiler, run_context: RunContext) -> None:
    result = compiler.compile("Lead Software Engineer\n\nRequired:\n- Python\n", run_context)
    assert result.ok
    assert result.value.target_seniority == "lead"


@pytest.mark.covers("FR-401")
def test_title_extraction_from_markdown_heading(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    result = compiler.compile("# Senior Role\n\nRequired:\n- Python\n", run_context)
    assert result.ok
    assert result.value.title == "Senior Role"


@pytest.mark.covers("FR-401")
def test_education_extraction_bachelors_in_computer_science(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    source = (
        "Role\n\nRequired:\n- Python\n\n"
        "Education:\n- Bachelor's degree in Computer Science or equivalent experience\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    assert result.value.education is not None
    assert result.value.education.min_level == "bachelors"
    assert result.value.education.fields == ("computer science",)
    assert result.value.education.equivalent_experience_allowed is True
    assert result.value.education.knockout is False


@pytest.mark.covers("FR-401")
def test_education_extraction_masters_degree_knockout(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    source = (
        "Role\n\nRequired:\n- Python\n\nEducation:\n- Master's degree required. Degree required.\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    assert result.value.education is not None
    assert result.value.education.min_level == "masters"
    assert result.value.education.knockout is True


@pytest.mark.covers("FR-401")
def test_domain_extraction(compiler: JobSpecCompiler, run_context: RunContext) -> None:
    source = "Role\n\nMust have:\n- Python\n\nDomain: fintech\n"
    result = compiler.compile(source, run_context)
    assert result.ok
    assert result.value.domain is not None
    assert result.value.domain.industry == "fintech"


@pytest.mark.covers("FR-401")
def test_education_extraction_preferred_degree_in_field(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """A JD with "Bachelor's or Master's (preferred) degree in X" should capture X."""
    source = (
        "Role\n\nRequired:\n- Python\n\n"
        "What We’re Looking for (Minimum Qualifications):\n"
        "Bachelor's or Master's (preferred) degree in Computer Science or a related field\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    assert result.value.education is not None
    assert result.value.education.min_level == "bachelors"
    assert result.value.education.fields == ("computer science",)


@pytest.mark.covers("FR-401")
def test_certification_extraction_ignores_skill_lines(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """General skill lines mentioning AWS/Azure must not be modelled as certifications."""
    source = (
        "Role\n\nRequired:\n- Python\n\n"
        "Familiarity with cloud platforms like AWS or Azure, containerization, and virtualization\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    assert result.value.certifications == ()


@pytest.mark.covers("FR-401")
def test_prose_required_skills_from_minimum_qualifications(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """Prose under a "Minimum Qualifications" heading is split into required skills."""
    source = (
        "Role\n\n"
        "What We’re Looking for (Minimum Qualifications):\n"
        "Expertise in Linux kernel networking, NAT, and Python programming\n"
        "Proficiency in Go or Rust\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    required = {s.canonical for s in result.value.required_skills}
    assert "linux kernel networking" in required
    assert "nat" in required
    assert "python programming" in required
    assert "go" in required
    assert "rust" in required


@pytest.mark.covers("FR-401")
def test_prose_preferred_skills_from_preferred_qualifications(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """Prose under a "Preferred Qualifications" heading is split into preferred skills."""
    source = (
        "Role\n\n"
        "What Will Make You Stand Out (Preferred Qualifications):\n"
        "Experience with AWS or Azure, Docker and Kubernetes\n\n"
        "Base Pay Range\n$100,000 - $200,000 USD\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    preferred = {s.canonical for s in result.value.preferred_skills}
    assert "aws" in preferred
    assert "azure" in preferred
    assert "docker" in preferred
    assert "kubernetes" in preferred
    # Footer lines must not be collected as preferred skills.
    assert "$100" not in preferred
    assert "200,000 usd" not in preferred


@pytest.mark.covers("FR-401")
def test_section_terminator_stops_preferred_section(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """Lines like "#LI-Hybrid" or "Zscaler’s salary ranges..." close the active section."""
    source = (
        "Role\n\nPreferred:\n- Rust\n\n"
        "#LI-Hybrid\n"
        "Zscaler’s salary ranges are benchmarked...\n"
        "Base Pay Range\n$100,000 USD\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    preferred = {s.canonical for s in result.value.preferred_skills}
    assert "rust" in preferred
    assert "salary" not in preferred
    assert "$100" not in preferred


@pytest.mark.covers("FR-401")
def test_responsibilities_heading_with_parenthetical(
    compiler: JobSpecCompiler, run_context: RunContext
) -> None:
    """What you’ll do (Role Expectations) is recognised as responsibilities."""
    source = (
        "Role\n\nWhat you’ll do (Role Expectations):\n"
        "Design scalable systems and review PRDs.\n\n"
        "Who You Are (Success Profile):\n"
        "You act like an owner.\n"
    )
    result = compiler.compile(source, run_context)
    assert result.ok
    assert len(result.value.responsibility_chunks) == 1
    assert "design scalable systems" in result.value.responsibility_chunks[0].text.lower()
    # The success-profile paragraph should not leak into responsibilities.
    assert not any("owner" in rc.text.lower() for rc in result.value.responsibility_chunks)
