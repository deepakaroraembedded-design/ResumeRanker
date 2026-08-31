from __future__ import annotations

import pytest

from resume_ranker.models.ontology import TitleMatch
from resume_ranker.ontology import TitleTaxonomy


@pytest.fixture
def taxonomy() -> TitleTaxonomy:
    return TitleTaxonomy()


class TestNormalise:
    def test_senior_software_engineer(self, taxonomy: TitleTaxonomy) -> None:
        match = taxonomy.normalise("Senior Software Engineer")
        assert match is not None
        assert match.family == "software_engineering"
        assert match.seniority == "senior"

    def test_data_scientist(self, taxonomy: TitleTaxonomy) -> None:
        match = taxonomy.normalise("Data Scientist")
        assert match is not None
        assert match.family == "data_science"
        assert match.seniority == "mid"

    def test_rockstar_developer(self, taxonomy: TitleTaxonomy) -> None:
        match = taxonomy.normalise("Rockstar Developer")
        assert match is not None
        assert match.family == "software_engineering"
        assert match.seniority == "senior"

    def test_ninja_coder(self, taxonomy: TitleTaxonomy) -> None:
        match = taxonomy.normalise("Ninja Coder")
        assert match is not None
        assert match.family == "software_engineering"
        assert match.seniority == "senior"

    def test_associate_director_ii(self, taxonomy: TitleTaxonomy) -> None:
        match = taxonomy.normalise("Associate Director II")
        assert match is not None
        assert match.family == "management"
        assert match.seniority == "director"
        assert "ii" not in match.normalised

    def test_unknown_title_returns_none(self, taxonomy: TitleTaxonomy) -> None:
        assert taxonomy.normalise("Grand Panjandrum") is None


class TestSimilarity:
    def test_same_family(self, taxonomy: TitleTaxonomy) -> None:
        a = TitleMatch(family="software_engineering", seniority="senior", raw="a", normalised="a")
        b = TitleMatch(family="software_engineering", seniority="junior", raw="b", normalised="b")
        assert taxonomy.similarity(a, b) == 1.0

    def test_adjacent_family(self, taxonomy: TitleTaxonomy) -> None:
        a = TitleMatch(family="software_engineering", seniority="senior", raw="a", normalised="a")
        b = TitleMatch(family="data_engineering", seniority="senior", raw="b", normalised="b")
        assert taxonomy.similarity(a, b) == 0.55

    def test_unrelated_family(self, taxonomy: TitleTaxonomy) -> None:
        a = TitleMatch(family="product_management", seniority="senior", raw="a", normalised="a")
        b = TitleMatch(family="security", seniority="senior", raw="b", normalised="b")
        assert taxonomy.similarity(a, b) == 0.15


class TestSeniorityGap:
    def test_gap(self, taxonomy: TitleTaxonomy) -> None:
        senior = TitleMatch(
            family="software_engineering", seniority="senior", raw="a", normalised="a"
        )
        junior = TitleMatch(
            family="software_engineering", seniority="junior", raw="b", normalised="b"
        )
        assert taxonomy.seniority_gap(senior, junior) > 0
        assert taxonomy.seniority_gap(junior, senior) < 0
