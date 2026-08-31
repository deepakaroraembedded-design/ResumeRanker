from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings, strategies

from resume_ranker.models.ontology import TitleMatch
from resume_ranker.ontology import SkillOntology, TitleTaxonomy


@pytest.fixture
def ontology() -> SkillOntology:
    return SkillOntology()


@pytest.fixture
def taxonomy() -> TitleTaxonomy:
    return TitleTaxonomy()


KNOWN_CANONICALS = [
    "python",
    "py",
    "SQL",
    "PyThOn",
    "apache-spark",
    "Spark",
]

CASE_STABLE_CANONICALS = [
    "python",
    "javascript",
    "sql",
    "apache-spark",
    "pandas",
    "tensorflow",
    "scrum",
]


@given(raw=strategies.sampled_from(KNOWN_CANONICALS))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_canonicalise_is_idempotent(raw: str, ontology: SkillOntology) -> None:
    first = ontology.canonicalise(raw)
    assert first is not None
    second = ontology.canonicalise(first.canonical)
    assert second is not None
    assert first.canonical == second.canonical


@given(canonical=strategies.sampled_from(CASE_STABLE_CANONICALS))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_canonicalise_is_case_stable(canonical: str, ontology: SkillOntology) -> None:
    upper_match = ontology.canonicalise(canonical.upper())
    lower_match = ontology.canonicalise(canonical.lower())
    assert upper_match is not None
    assert lower_match is not None
    assert upper_match.canonical == lower_match.canonical


@given(
    family=strategies.sampled_from(
        [
            "software_engineering",
            "data_engineering",
            "data_science",
            "machine_learning",
            "product_management",
        ]
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_title_similarity_is_symmetric(family: str, taxonomy: TitleTaxonomy) -> None:
    a = TitleMatch(family=family, seniority="senior", raw="a", normalised="a")
    b = TitleMatch(family="software_engineering", seniority="senior", raw="b", normalised="b")
    assert taxonomy.similarity(a, b) == taxonomy.similarity(b, a)
