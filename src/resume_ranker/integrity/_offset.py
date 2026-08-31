from __future__ import annotations

from resume_ranker.models.source import TextBlock

_JOINER = "\n"


def build_text(
    blocks: tuple[TextBlock, ...], separator: str = _JOINER
) -> tuple[str, list[tuple[int, int]]]:
    """Join block texts and return the full text plus per-block character spans.

    The returned spans map each block to its position in the joined text, so that
    IntegrityFinding.spans satisfy the quote-equals-span contract when the
    source text is reconstructed in the same way.
    """
    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    offset = 0
    for block in blocks:
        if offset > 0:
            parts.append(separator)
            offset += len(separator)
        start = offset
        text = block.text
        offset += len(text)
        parts.append(text)
        spans.append((start, offset))
    return "".join(parts), spans
