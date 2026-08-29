from __future__ import annotations

import pytest

from ats_scan.models.ontology import SkillRelation
from ats_scan.ontology import SkillOntology


class _SameVectorEmbeddingClient:
    """Stub embedding client that returns identical vectors for every text."""

    dimensions = 384

    async def embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [tuple(1.0 for _ in range(self.dimensions)) for _ in texts]


@pytest.fixture
def ontology() -> SkillOntology:
    return SkillOntology()


@pytest.fixture
def embedded_ontology() -> SkillOntology:
    return SkillOntology(embeddings=_SameVectorEmbeddingClient())


class TestCanonicalise:
    def test_exact_match(self, ontology: SkillOntology) -> None:
        match = ontology.canonicalise("python")
        assert match is not None
        assert match.canonical == "python"
        assert match.relation == SkillRelation.EXACT

    def test_alias_match(self, ontology: SkillOntology) -> None:
        match = ontology.canonicalise("py")
        assert match is not None
        assert match.canonical == "python"
        assert match.relation == SkillRelation.ALIAS

    def test_case_and_punctuation_insensitive_match(self, ontology: SkillOntology) -> None:
        match = ontology.canonicalise("  PyThOn! ")
        assert match is not None
        assert match.canonical == "python"
        assert match.relation == SkillRelation.EXACT

    def test_fuzzy_match_above_threshold(self, ontology: SkillOntology) -> None:
        match = ontology.canonicalise("apach-spark")
        assert match is not None
        assert match.canonical == "apache-spark"
        assert match.relation == SkillRelation.FUZZY

    def test_embedding_match_when_client_supplied(self, embedded_ontology: SkillOntology) -> None:
        match = embedded_ontology.canonicalise("zzzznotinontology")
        assert match is not None
        assert match.relation == SkillRelation.EMBEDDING
        assert match.canonical in embedded_ontology._canonical_set

    def test_unmapped_string_returns_none(self, ontology: SkillOntology) -> None:
        assert ontology.canonicalise("totally-unknown-thing-xyz") is None


class TestRelation:
    def test_exact_relation(self, ontology: SkillOntology) -> None:
        assert ontology.relation("python", "python") == SkillRelation.EXACT

    def test_alias_relation(self, ontology: SkillOntology) -> None:
        assert ontology.relation("py", "python") == SkillRelation.ALIAS

    def test_child_relation(self, ontology: SkillOntology) -> None:
        assert ontology.relation("apache-spark-core", "apache-spark") == SkillRelation.CHILD

    def test_parent_relation(self, ontology: SkillOntology) -> None:
        assert ontology.relation("apache-spark", "apache-spark-core") == SkillRelation.PARENT

    def test_unrelated_relation(self, ontology: SkillOntology) -> None:
        assert ontology.relation("python", "apache-spark") == SkillRelation.NONE


class TestIsTimeless:
    def test_foundation_skills_are_timeless(self, ontology: SkillOntology) -> None:
        assert ontology.is_timeless("python")
        assert ontology.is_timeless("sql")
        assert ontology.is_timeless("linear-algebra")

    def test_version_sensitive_skills_are_not_timeless(self, ontology: SkillOntology) -> None:
        assert not ontology.is_timeless("apache-spark")
        assert not ontology.is_timeless("react")


class TestIdempotence:
    def test_canonicalise_is_idempotent_and_case_stable(self, ontology: SkillOntology) -> None:
        variants = ["Python", " python ", "PYTHON", "PyThOn"]
        canonicals = {
            ontology.canonicalise(v).canonical for v in variants if ontology.canonicalise(v)
        }
        assert canonicals == {"python"}
