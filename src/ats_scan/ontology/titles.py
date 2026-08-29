from __future__ import annotations

import re
from pathlib import Path

from ats_scan.models.ontology import TitleMatch
from ats_scan.ontology.loader import load_titles

_TITLE_PUNCT_RE = re.compile(r"[^\w\s]+")
_ROMAN_RE = re.compile(r"\b(i{1,3}|iv|v|vi{1,3}|ix|x)\b")
_NUMERIC_SUFFIX_RE = re.compile(r"\b\d+\b")


class TitleTaxonomy:
    """Normalised job-title taxonomy implementing the TitleTaxonomy protocol (TRD §3.5)."""

    def __init__(self, data_path: str | Path | None = None) -> None:
        """Load the title taxonomy from a versioned JSON directory."""
        resolved_path = Path(data_path) if data_path is not None else self._default_path()
        self._data = load_titles(resolved_path)

    @staticmethod
    def _default_path() -> Path:
        """Return the default title taxonomy directory shipped with the component."""
        return Path(__file__).resolve().parents[3] / "data" / "titles" / "2026.07"

    def normalise(self, raw_title: str) -> TitleMatch | None:
        """Map a raw job title to a family + seniority pair (FR-504)."""
        if not raw_title or not raw_title.strip():
            return None

        cleaned = self._clean_title(raw_title)
        if cleaned in self._data.patterns:
            pattern = self._data.patterns[cleaned]
            return TitleMatch(
                family=pattern["family"],
                seniority=pattern["seniority"],
                raw=raw_title,
                normalised=cleaned,
            )

        tokens = cleaned.split()
        family: str | None = None
        seniority: str | None = None
        inflation_tokens: list[str] = []

        # Inflated titles such as "Ninja" or "Rockstar" map to a default family
        # and a senior level unless a more specific signal is present.
        for token in tokens:
            if token in self._data.inflation:
                inflation_tokens.append(token)
                family = family or self._data.inflation[token]
                seniority = seniority or "senior"

        # Highest seniority token wins.
        for token in tokens:
            if token in self._data.seniority_index and (
                seniority is None
                or self._data.seniority_index[token] > self._data.seniority_index[seniority]
            ):
                seniority = token

        # Family detection from keywords (longest match first).
        family = family or self._detect_family(cleaned)
        if family is None:
            return None

        seniority = seniority or "mid"
        normalised = " ".join(t for t in tokens if t not in self._data.inflation)
        return TitleMatch(
            family=family,
            seniority=seniority,
            raw=raw_title,
            normalised=normalised,
        )

    def similarity(self, a: TitleMatch, b: TitleMatch) -> float:
        """Return the family similarity between two title matches.

        Implements the S5 title similarity scale (TRD §5.3.5): exact family
        1.0, adjacent family 0.55, otherwise 0.15. Adjacency is tested in both
        directions so the result is symmetric even if the data graph is not.
        """
        if a.family == b.family:
            return 1.0
        a_adjacent = self._data.adjacency.get(a.family, frozenset())
        b_adjacent = self._data.adjacency.get(b.family, frozenset())
        if b.family in a_adjacent or a.family in b_adjacent:
            return 0.55
        return 0.15

    def seniority_gap(self, role: TitleMatch, target: TitleMatch) -> int:
        """Return the ordinal difference between the role and target seniorities."""
        role_index = self._data.seniority_index.get(role.seniority)
        target_index = self._data.seniority_index.get(target.seniority)
        if role_index is None or target_index is None:
            return 0
        return role_index - target_index

    @staticmethod
    def _clean_title(raw_title: str) -> str:
        """Lower-case, strip punctuation, remove numeric/roman suffixes, collapse spaces."""
        lower = raw_title.strip().lower()
        lower = _TITLE_PUNCT_RE.sub(" ", lower)
        lower = _ROMAN_RE.sub(" ", lower)
        lower = _NUMERIC_SUFFIX_RE.sub(" ", lower)
        return " ".join(lower.split())

    def _detect_family(self, cleaned: str) -> str | None:
        """Pick the family whose keyword appears in the cleaned title."""
        best_family: str | None = None
        best_length = 0
        for family, keywords in self._data.family_keywords.items():
            for keyword in keywords:
                if keyword in cleaned and len(keyword) > best_length:
                    best_family = family
                    best_length = len(keyword)
        return best_family
