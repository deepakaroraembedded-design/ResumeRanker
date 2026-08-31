from __future__ import annotations

import re
from pathlib import Path

from resume_ranker.ontology.loader import load_employers

_EMPLOYER_PUNCT_RE = re.compile(r"[^\w\s]+")


class EmployerNormalizer:
    """Normalise employer names for de-duplication and tenure computation (FR-505)."""

    def __init__(self, data_path: str | Path | None = None) -> None:
        """Load employer normalisation data from a versioned JSON directory."""
        resolved_path = Path(data_path) if data_path is not None else self._default_path()
        self._data = load_employers(resolved_path)

    @staticmethod
    def _default_path() -> Path:
        """Return the default employer data directory shipped with the component."""
        return Path(__file__).resolve().parents[3] / "data" / "ontology" / "2026.07"

    def normalise(self, raw: str) -> str | None:
        """Strip legal suffixes and resolve aliases, returning a canonical key.

        Returns ``None`` for empty input.
        """
        if not raw or not raw.strip():
            return None

        cleaned = _EMPLOYER_PUNCT_RE.sub(" ", raw.strip().lower())
        cleaned = " ".join(cleaned.split())

        # Alias replacement (longest match first).
        for alias, canonical in sorted(self._data.aliases.items(), key=lambda kv: -len(kv[0])):
            if cleaned == alias or (" " + alias + " " in " " + cleaned + " "):
                cleaned = canonical
                break

        tokens = cleaned.split()
        filtered = [token for token in tokens if token not in self._data.suffixes]
        return " ".join(filtered) if filtered else None
