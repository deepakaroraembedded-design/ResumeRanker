from __future__ import annotations

from pathlib import Path

from resume_ranker.ontology import (
    SkillOntology,
    TitleTaxonomy,
    from_config,
    load_employers,
    load_skills,
    load_titles,
)
from resume_ranker.ontology.loader import EmployerData, TitleData


def _data_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "ontology" / "2026.07"


def _title_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "titles" / "2026.07"


class TestLoadSkills:
    def test_loads_minimum_canonical_skills(self) -> None:
        entries, alias_map, version = load_skills(_data_root())
        assert version == "2026.07"
        assert len(entries) >= 1500
        assert alias_map["py"] == "python"
        assert alias_map["spark"] == "apache-spark"

    def test_timeless_skills_are_loaded(self) -> None:
        entries, _alias_map, _version = load_skills(_data_root())
        timeless = {e.canonical for e in entries if e.timeless}
        assert "python" in timeless
        assert "sql" in timeless
        assert "statistics" in timeless
        assert "linear-algebra" in timeless


class TestLoadTitles:
    def test_loads_title_taxonomy(self) -> None:
        data = load_titles(_title_root())
        assert isinstance(data, TitleData)
        assert data.version == "2026.07"
        assert "senior" in data.seniority_levels
        assert "software_engineering" in data.families


class TestLoadEmployers:
    def test_loads_employer_data(self) -> None:
        data = load_employers(_data_root())
        assert isinstance(data, EmployerData)
        assert data.version == "2026.07"
        assert "inc" in data.suffixes
        assert data.aliases["ibm"] == "international business machines"


class TestFactory:
    def test_from_config_returns_instances(self) -> None:
        ontology, titles = from_config()
        assert isinstance(ontology, SkillOntology)
        assert isinstance(titles, TitleTaxonomy)
        assert ontology.version == "2026.07"
