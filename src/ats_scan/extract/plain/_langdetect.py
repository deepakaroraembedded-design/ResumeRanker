"""Lightweight stopword-based language detector for C-03 extractors.

No third-party language-detection library is pinned, so FR-209 is satisfied with
a deterministic stopword classifier over the configured set of supported
languages.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

_TOKEN_CLEAN = re.compile(r"[^\w\s-]+")

_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "this",
            "that",
            "these",
            "those",
            "i",
            "we",
            "you",
            "he",
            "she",
            "it",
            "they",
            "my",
            "our",
            "your",
            "their",
            "his",
            "her",
        }
    ),
    "es": frozenset(
        {
            "el",
            "la",
            "los",
            "las",
            "un",
            "una",
            "y",
            "o",
            "pero",
            "en",
            "de",
            "a",
            "con",
            "por",
            "para",
            "del",
            "al",
            "es",
            "son",
            "está",
            "están",
            "lo",
            "le",
            "se",
        }
    ),
    "fr": frozenset(
        {
            "le",
            "la",
            "les",
            "un",
            "une",
            "et",
            "ou",
            "mais",
            "dans",
            "de",
            "du",
            "à",
            "au",
            "pour",
            "par",
            "avec",
            "est",
            "sont",
            "ce",
            "cette",
            "ces",
            "je",
            "nous",
            "vous",
        }
    ),
    "de": frozenset(
        {
            "der",
            "die",
            "das",
            "ein",
            "eine",
            "und",
            "oder",
            "aber",
            "in",
            "von",
            "zu",
            "für",
            "mit",
            "auf",
            "ist",
            "sind",
            "war",
            "waren",
            "wir",
            "ihr",
            "sie",
            "ich",
        }
    ),
    "it": frozenset(
        {
            "il",
            "la",
            "i",
            "le",
            "un",
            "una",
            "e",
            "o",
            "ma",
            "in",
            "di",
            "a",
            "con",
            "per",
            "da",
            "è",
            "sono",
            "questo",
            "questa",
            "noi",
            "voi",
            "loro",
        }
    ),
    "pt": frozenset(
        {
            "o",
            "a",
            "os",
            "as",
            "um",
            "uma",
            "e",
            "ou",
            "mas",
            "em",
            "de",
            "para",
            "com",
            "por",
            "é",
            "são",
            "este",
            "esta",
            "estes",
            "nós",
            "vocês",
            "eles",
        }
    ),
    "nl": frozenset(
        {
            "de",
            "het",
            "een",
            "en",
            "of",
            "maar",
            "in",
            "op",
            "voor",
            "met",
            "door",
            "van",
            "is",
            "zijn",
            "was",
            "waren",
            "wij",
            "jullie",
            "zij",
        }
    ),
}


def detect_language(text: str, supported: Sequence[str]) -> tuple[str, float]:
    """Return the best language tag and confidence for *text*.

    The classifier scores a text by counting known stopwords for each supported
    language.  This is intentionally simple: C-03 is not a language-analysis
    stage and only needs to record the primary language and flag documents that
    fall outside the configured set.

    Args:
        text: Normalised or raw text extracted from the document.
        supported: ISO-639-1 language tags configured as accepted; used only as
            a fallback default when no known stopwords are found.

    Returns:
        A ``(language, confidence)`` tuple for the best-matching language among
        all known stopword lists.  Confidence is the share of stopwords among
        all candidate tokens, bounded to ``[0.0, 1.0]``.  If no stopwords are
        found, the first supported language (defaulting to ``"en"``) is
        returned with ``0.0`` confidence.
    """
    tokens = [_TOKEN_CLEAN.sub("", token.lower()) for token in text.split()]
    tokens = [token for token in tokens if token]

    counts: dict[str, int] = dict.fromkeys(_STOPWORDS, 0)
    for token in tokens:
        for lang, stopwords in _STOPWORDS.items():
            if token in stopwords:
                counts[lang] += 1

    if not any(counts.values()):
        supported = tuple(supported) if supported else ("en",)
        return supported[0] if supported[0] in _STOPWORDS else "en", 0.0

    best = max(counts, key=lambda lang: (counts[lang], lang))
    total = len(tokens) or 1
    confidence = min(counts[best] / total, 1.0)
    return best, confidence
