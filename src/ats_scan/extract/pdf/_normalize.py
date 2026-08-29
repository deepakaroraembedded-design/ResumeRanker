from __future__ import annotations

import re
import unicodedata

# Characters that pdfplumber may still emit but that must be removed before
# downstream processing (FR-210).
_BIDI_CONTROLS = frozenset(
    "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff"
)

_ZERO_WIDTH = frozenset("\u200b\u200c\u200d\u2060")

_SOFT_HYPHEN = "\u00ad"

_CONTROL_REPLACEMENT = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def normalize_text(text: str) -> str:
    """Return a normalised version of *text* per FR-210.

    * Unicode NFKC compatibility decomposition.
    * Strip zero-width and bidirectional control characters.
    * Remove soft hyphens.
    * Replace remaining C0/C1 control characters with a space.
    * Collapse horizontal whitespace and trim each line.
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if char not in _BIDI_CONTROLS and char not in _ZERO_WIDTH)
    text = text.replace(_SOFT_HYPHEN, "")
    text = _CONTROL_REPLACEMENT.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
