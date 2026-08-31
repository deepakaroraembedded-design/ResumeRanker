"""Unicode text normalisation shared by the plain and office extractors.

This module provides a stop-gap implementation of the C-02/C-03 Unicode
normalisation contract required by FR-210.  It should be replaced by an import
from ``resume_ranker.models.source`` once contract change C-03-001 is merged.
"""

from __future__ import annotations

import unicodedata

# Zero-width and bidirectional control characters removed by FR-210.
_DELETE_CHARACTERS: str = (
    "\u200b"  # zero width space
    "\u200c"  # zero width non-joiner
    "\u200d"  # zero width joiner
    "\ufeff"  # zero width no-break space / BOM
    "\u202a\u202b\u202c\u202d\u202e"  # bidi embedding / override / PDF
    "\u2066\u2067\u2068\u2069"  # bidi isolate initiators / PDI
)
_DELETE_TABLE = str.maketrans("", "", _DELETE_CHARACTERS)


def normalise_text(text: str) -> str:
    """Return the shared Unicode normalisation of *text*.

    Implements FR-210: Unicode NFKC normalisation, removal of zero-width
    characters, and removal of bidirectional control characters.  Ligatures
    such as ``ﬁ`` and ``ﬂ`` are handled by NFKC.

    Args:
        text: Raw decoded text.

    Returns:
        Normalised text ready for downstream structuring and evidence span
        indexing.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_DELETE_TABLE)
    return text
