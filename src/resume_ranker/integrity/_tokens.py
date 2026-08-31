from __future__ import annotations

import re


def tokenize(text: str) -> list[str]:
    """Return lowercase word tokens from *text*.

    Tokens are contiguous runs of word characters.  This is intentionally
    simple so that detectors behave identically across languages and do not
    depend on a heavy NLP model.
    """
    return re.findall(r"\b\w+\b", text.lower())
