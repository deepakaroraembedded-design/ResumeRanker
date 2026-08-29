from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pdfplumber

from ats_scan.extract.pdf._config import PdfExtractionConfig
from ats_scan.extract.pdf._normalize import normalize_text


@dataclass(frozen=True)
class Glyph:
    """A single glyph extracted from a PDF page."""

    page: int
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    font_size: float
    color: tuple[float, float, float] | None
    render_mode: int | None
    is_in_table: bool = False


@dataclass(frozen=True)
class LineBlock:
    """A logical line of text together with its source metadata."""

    page: int
    bbox: tuple[float, float, float, float]
    text: str
    font_size: float | None
    color: tuple[float, float, float] | None
    render_mode: int | None


def _glyphs_from_page(page: pdfplumber.page.Page, page_number: int) -> list[Glyph]:
    """Convert pdfplumber character objects into normalised glyphs."""
    glyphs: list[Glyph] = []
    for raw_char in page.chars:
        char = dict(raw_char) if not isinstance(raw_char, dict) else raw_char
        text = str(char.get("text", ""))
        if not text:
            continue
        x0 = float(char.get("x0", 0.0))
        top = float(char.get("top", 0.0))
        x1 = float(char.get("x1", x0))
        bottom = float(char.get("bottom", top))
        font_size = float(char.get("size", 0.0))
        color = _color_from_char(char)
        render_mode = int(char.get("render_mode", 0)) if "render_mode" in char else None
        glyphs.append(
            Glyph(
                page=page_number,
                text=text,
                x0=x0,
                top=top,
                x1=x1,
                bottom=bottom,
                font_size=font_size,
                color=color,
                render_mode=render_mode,
            )
        )
    return glyphs


def _color_from_char(char: dict[str, Any]) -> tuple[float, float, float] | None:
    """Return the fill colour of *char* as a normalised RGB triple."""
    raw = char.get("non_stroking_color") or char.get("stroking_color")
    if raw is None:
        return None

    if isinstance(raw, (list, tuple)):
        values = [float(v) for v in raw if isinstance(v, (int, float))]
        if len(values) == 3:
            return _normalize_rgb(values)
        if len(values) == 1:
            return _normalize_rgb((values[0], values[0], values[0]))
        return None

    if isinstance(raw, (int, float)):
        return _normalize_rgb((float(raw), float(raw), float(raw)))

    return None


def _normalize_rgb(values: Sequence[float]) -> tuple[float, float, float]:
    """Scale an RGB triple to the [0, 1] range if it is given in [0, 255]."""
    max_value = max(values) if values else 1.0
    scale = 255.0 if max_value > 1.0 else 1.0
    return (values[0] / scale, values[1] / scale, values[2] / scale)


def _visual_top(glyph: Glyph) -> float:
    """Return the upper boundary of *glyph* in pdfplumber coordinates."""
    return max(glyph.top, glyph.bottom)


def _visual_bottom(glyph: Glyph) -> float:
    """Return the lower boundary of *glyph* in pdfplumber coordinates."""
    return min(glyph.top, glyph.bottom)


def _line_blocks_from_glyphs(
    glyphs: Sequence[Glyph], page_width: float, config: PdfExtractionConfig
) -> list[LineBlock]:
    """Group *glyphs* into column-major, top-to-bottom line blocks."""
    if not glyphs:
        return []

    column_gap = max(config.column_gap_share * page_width, 2.0)
    columns = _cluster_columns(glyphs, column_gap)

    lines: list[LineBlock] = []
    for column in columns:
        column_lines = _cluster_lines(column, config)
        lines.extend(column_lines)
    # Reading order: columns left-to-right, then top-to-bottom (descending upper).
    lines.sort(key=lambda line: (line.bbox[0], -line.bbox[1]))
    return lines


def _cluster_columns(glyphs: Sequence[Glyph], gap: float) -> list[list[Glyph]]:
    """Cluster glyphs into columns based on horizontal gaps."""
    ordered = sorted(glyphs, key=lambda g: g.x0)
    columns: list[list[Glyph]] = []
    current: list[Glyph] = []
    for glyph in ordered:
        if not current:
            current.append(glyph)
            continue
        if glyph.x0 - current[-1].x1 > gap:
            columns.append(current)
            current = [glyph]
        else:
            current.append(glyph)
    if current:
        columns.append(current)
    return columns


def _cluster_lines(glyphs: Sequence[Glyph], config: PdfExtractionConfig) -> list[LineBlock]:
    """Cluster glyphs within a single column into visual lines.

    In pdfplumber coordinates the origin is at the bottom of the page, so visual
    top-to-bottom order corresponds to descending upper boundaries.  Glyphs whose
    upper boundaries are close (within a fraction of the font size) are treated
    as one line.
    """
    if not glyphs:
        return []

    line_gap = max(0.3 * _median_font_size(glyphs), 2.0)
    sorted_glyphs = sorted(glyphs, key=lambda g: (-_visual_top(g), g.x0))

    lines: list[list[Glyph]] = []
    current: list[Glyph] = []
    for glyph in sorted_glyphs:
        if not current:
            current.append(glyph)
            continue
        previous_top = _visual_top(current[-1])
        current_top = _visual_top(glyph)
        # A new line starts when the current glyph is visually below the
        # previous line by more than the line gap.
        if previous_top - current_top > line_gap:
            lines.append(current)
            current = [glyph]
        else:
            current.append(glyph)
    if current:
        lines.append(current)

    return [_build_line(line) for line in lines]


def _build_line(glyphs: Sequence[Glyph]) -> LineBlock:
    """Build a single line block from a sequence of glyphs."""
    ordered = sorted(glyphs, key=lambda g: g.x0)
    parts: list[str] = []
    previous_x1: float | None = None
    previous_font_size: float = 0.0

    for glyph in ordered:
        if glyph.text.isspace():
            parts.append(" ")
            previous_x1 = glyph.x1
            continue

        if previous_x1 is not None:
            gap = glyph.x0 - previous_x1
            space_width = max(0.25 * previous_font_size, 1.0)
            if gap > space_width:
                parts.append(" ")
        parts.append(glyph.text)
        previous_x1 = glyph.x1
        if glyph.font_size > 0:
            previous_font_size = glyph.font_size

    text = normalize_text("".join(parts))
    x0 = ordered[0].x0
    upper = max(_visual_top(g) for g in ordered)
    x1 = ordered[-1].x1
    lower = min(_visual_bottom(g) for g in ordered)
    font_size = _average([g.font_size for g in ordered if g.font_size > 0], default=0.0)
    color = _average_color([g.color for g in ordered if g.color is not None])
    render_mode = next((g.render_mode for g in ordered if g.render_mode is not None), None)
    return LineBlock(
        page=ordered[0].page,
        bbox=(x0, upper, x1, lower),
        text=text,
        font_size=font_size if font_size > 0 else None,
        color=color,
        render_mode=render_mode,
    )


def _median_font_size(glyphs: Sequence[Glyph]) -> float:
    sizes = sorted(g.font_size for g in glyphs if g.font_size > 0)
    if not sizes:
        return 12.0
    mid = len(sizes) // 2
    return sizes[mid] if len(sizes) % 2 else (sizes[mid - 1] + sizes[mid]) / 2


def _average(values: Sequence[float], default: float = 0.0) -> float:
    if not values:
        return default
    return sum(values) / len(values)


def _average_color(
    colors: Sequence[tuple[float, float, float]],
) -> tuple[float, float, float] | None:
    if not colors:
        return None
    r = sum(c[0] for c in colors) / len(colors)
    g = sum(c[1] for c in colors) / len(colors)
    b = sum(c[2] for c in colors) / len(colors)
    return (r, g, b)


def _drop_repeated_headers_footers(
    blocks: Sequence[LineBlock],
    page_heights: dict[int, float],
    config: PdfExtractionConfig,
) -> list[LineBlock]:
    """Remove repeated headers and footers across pages (FR-204)."""
    if len(page_heights) < config.header_footer_min_pages:
        return list(blocks)

    n_pages = len(page_heights)
    threshold = max(config.header_footer_min_pages, int(config.header_footer_min_share * n_pages))
    counts: dict[tuple[str, str], int] = {}
    indices: dict[tuple[str, str], list[int]] = {}

    for index, block in enumerate(blocks):
        height = page_heights.get(block.page, 0.0)
        if height <= 0:
            continue
        margin = height * config.header_footer_margin_share
        upper = max(block.bbox[1], block.bbox[3])
        lower = min(block.bbox[1], block.bbox[3])
        # pdfplumber coordinates: origin at bottom, so header = large upper value,
        # footer = small lower value.
        if upper > height - margin:
            band = "header"
        elif lower < margin:
            band = "footer"
        else:
            continue

        key = (_repeat_key(block.text), band)
        counts[key] = counts.get(key, 0) + 1
        indices.setdefault(key, []).append(index)

    drop_indices = {
        idx for key, count in counts.items() if count >= threshold for idx in indices[key]
    }
    return [block for index, block in enumerate(blocks) if index not in drop_indices]


def _repeat_key(text: str) -> str:
    """Return a normalised form of *text* for repeated-block detection."""
    return "".join(ch.lower() for ch in text if ch.isalnum())
