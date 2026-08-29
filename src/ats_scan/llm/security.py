from __future__ import annotations

from collections.abc import Sequence

_BIDI_OVERRIDES: frozenset[int] = frozenset(
    {0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069}
)


def strip_control_chars(text: str) -> str:
    """Remove control characters and bidirectional overrides from *text*.

    Keeps tab, newline, carriage return, space and printable Unicode characters.
    This is part of the injection-hardening controls described in TRD §6.4.

    Args:
        text: Input string to clean.

    Returns:
        A copy of *text* with control characters removed.
    """
    allowed: frozenset[str] = frozenset({"\t", "\n", "\r", " "})
    result: list[str] = []
    for ch in text:
        code = ord(ch)
        if (ch in allowed or 0x20 <= code <= 0x7E or code >= 0xA0) and code not in _BIDI_OVERRIDES:
            result.append(ch)
    return "".join(result)


def remove_quarantined_spans(text: str, spans: Sequence[tuple[int, int]]) -> str:
    """Remove spans flagged by the injection detector from *text*.

    Spans are treated as half-open ``[start, end)`` character offsets. The
    implementation is order-independent and clamps out-of-bounds offsets.

    Args:
        text: Source text.
        spans: Offsets to remove.

    Returns:
        *text* with the specified spans removed.
    """
    if not spans:
        return text
    cleaned: list[str] = []
    previous = 0
    for start, end in sorted(spans):
        start = max(0, min(start, len(text)))
        end = max(start, min(end, len(text)))
        cleaned.append(text[previous:start])
        previous = end
    cleaned.append(text[previous:])
    return "".join(cleaned)


def truncate(text: str, max_length: int) -> str:
    """Truncate *text* to *max_length* characters.

    Args:
        text: Input string.
        max_length: Maximum allowed length.

    Returns:
        The first *max_length* characters of *text*.
    """
    return text[:max_length]
