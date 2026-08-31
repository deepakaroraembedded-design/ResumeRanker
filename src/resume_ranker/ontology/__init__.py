from __future__ import annotations

from resume_ranker.models.config import OntologyConfig
from resume_ranker.ontology.employer import EmployerNormalizer
from resume_ranker.ontology.loader import load_employers, load_skills, load_titles
from resume_ranker.ontology.match import SkillOntology
from resume_ranker.ontology.titles import TitleTaxonomy


def from_config(config: OntologyConfig | None = None) -> tuple[SkillOntology, TitleTaxonomy]:
    """Build the ontology and title taxonomy from a resolved configuration."""
    cfg = config if config is not None else OntologyConfig()
    ontology = SkillOntology(data_path=cfg.path)
    title_path = cfg.path.replace("ontology", "titles")
    titles = TitleTaxonomy(data_path=title_path)
    return ontology, titles


__all__ = [
    "EmployerNormalizer",
    "SkillOntology",
    "TitleTaxonomy",
    "from_config",
    "load_employers",
    "load_skills",
    "load_titles",
]
