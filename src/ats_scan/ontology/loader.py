from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillEntry:
    """One canonical skill node in the ontology graph."""

    canonical: str
    aliases: tuple[str, ...]
    parents: tuple[str, ...]
    children: tuple[str, ...]
    timeless: bool


@dataclass(frozen=True)
class TitleData:
    """Loaded title taxonomy data."""

    version: str
    seniority_levels: tuple[str, ...]
    seniority_index: dict[str, int]
    families: dict[str, dict[str, Any]]
    adjacency: dict[str, frozenset[str]]
    inflation: dict[str, str]
    patterns: dict[str, dict[str, str]]
    family_keywords: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class EmployerData:
    """Loaded employer normalisation data."""

    version: str
    suffixes: frozenset[str]
    aliases: dict[str, str]


def load_skills(path: str | Path) -> tuple[tuple[SkillEntry, ...], dict[str, str], str]:
    """Load the skill ontology from a versioned JSON directory.

    Returns the canonical entries, an alias map (alias -> canonical), and the version.
    """
    file_path = Path(path) / "skills.json"
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    version = raw["version"]
    entries: list[SkillEntry] = []
    alias_map: dict[str, str] = {}
    for item in raw["skills"]:
        canonical = item["canonical"].strip().lower()
        aliases = tuple(a.strip().lower() for a in item.get("aliases", []) if a.strip())
        for alias in aliases:
            alias_map[alias] = canonical
        # canonical also maps to itself for exact lookups.
        alias_map[canonical] = canonical
        entries.append(
            SkillEntry(
                canonical=canonical,
                aliases=aliases,
                parents=tuple(p.strip().lower() for p in item.get("parents", [])),
                children=tuple(c.strip().lower() for c in item.get("children", [])),
                timeless=bool(item.get("timeless", False)),
            )
        )
    return tuple(entries), alias_map, version


def load_titles(path: str | Path) -> TitleData:
    """Load the title taxonomy from a versioned JSON directory."""
    file_path = Path(path) / "titles.json"
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    seniority_levels = tuple(level.strip().lower() for level in raw["seniority_levels"])
    seniority_index = {level: idx for idx, level in enumerate(seniority_levels)}
    families = raw["families"]
    adjacency: dict[str, frozenset[str]] = {}
    family_keywords: dict[str, tuple[str, ...]] = {}
    for family, meta in families.items():
        adjacency[family] = frozenset(meta.get("adjacent", []))
        keywords = meta.get("keywords", [])
        if not keywords:
            keywords = [family.replace("_", " ")]
        family_keywords[family] = tuple(k.strip().lower() for k in keywords)

    inflation = {k.strip().lower(): v for k, v in raw.get("inflation", {}).items()}
    patterns = {
        k.strip().lower(): {"family": v["family"], "seniority": v["seniority"].strip().lower()}
        for k, v in raw.get("patterns", {}).items()
    }
    return TitleData(
        version=raw["version"],
        seniority_levels=seniority_levels,
        seniority_index=seniority_index,
        families=families,
        adjacency=adjacency,
        inflation=inflation,
        patterns=patterns,
        family_keywords=family_keywords,
    )


def load_employers(path: str | Path) -> EmployerData:
    """Load employer normalisation data from a versioned JSON directory."""
    file_path = Path(path) / "employers.json"
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    return EmployerData(
        version=raw["version"],
        suffixes=frozenset(s.strip().lower() for s in raw.get("legal_suffixes", [])),
        aliases={k.strip().lower(): v.strip().lower() for k, v in raw.get("aliases", {}).items()},
    )
