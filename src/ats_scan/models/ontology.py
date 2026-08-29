from __future__ import annotations

from enum import StrEnum

from pydantic.dataclasses import dataclass


class SkillRelation(StrEnum):
    """Relationship between two skill strings in the ontology."""

    EXACT = "exact"
    ALIAS = "alias"
    CHILD = "child"
    PARENT = "parent"
    FUZZY = "fuzzy"
    EMBEDDING = "embedding"
    NONE = "none"


@dataclass(frozen=True)
class SkillMatch:
    """Result of mapping a raw skill string to a canonical ontology entry."""

    canonical: str
    raw: str
    relation: SkillRelation


@dataclass(frozen=True)
class TitleMatch:
    """Result of normalising a job title."""

    family: str
    seniority: str
    raw: str
    normalised: str
