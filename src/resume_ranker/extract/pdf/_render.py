from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pdfplumber

from resume_ranker.extract.pdf._tokens import _color_from_char


def render_page_tokens(
    path: str, page_numbers: Sequence[int] | None = None
) -> list[dict[str, Any]]:
    """Render a PDF as a flat list of glyph tokens for corroboration (FR-205).

    Each token exposes the source page, bounding box, font size, fill colour and
    render mode.  This is the primitive C-06 consumes for text-layer vs. OCR
    comparison and hidden-text detection.
    """
    tokens: list[dict[str, Any]] = []
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages
        if page_numbers is not None:
            pages = [pages[n - 1] for n in page_numbers if 1 <= n <= len(pages)]
        for page_index, page in enumerate(pages, start=1):
            for raw_char in page.chars:
                char = dict(raw_char) if not isinstance(raw_char, dict) else raw_char
                text = str(char.get("text", ""))
                if not text:
                    continue
                x0 = float(char.get("x0", 0.0))
                top = float(char.get("top", 0.0))
                x1 = float(char.get("x1", x0))
                bottom = float(char.get("bottom", top))
                tokens.append(
                    {
                        "page": page_index
                        if page_numbers is None
                        else page_numbers[page_index - 1],
                        "text": text,
                        "bbox": (x0, top, x1, bottom),
                        "font_size": float(char.get("size", 0.0)) or None,
                        "color": _color_from_char(char),
                        "render_mode": (
                            int(char.get("render_mode", 0)) if "render_mode" in char else None
                        ),
                    }
                )
    return tokens
