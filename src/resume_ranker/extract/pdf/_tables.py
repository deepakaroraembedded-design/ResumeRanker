from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import pdfplumber

from resume_ranker.extract.pdf._normalize import normalize_text
from resume_ranker.extract.pdf._tokens import (
    Glyph,
    _build_line,
    _glyphs_from_page,
    _visual_top,
)


def _table_visual_upper(table: Any) -> float:
    """Return the upper (visually higher) y-coordinate of *table*."""
    first_cell = table.rows[0].cells[0] if table.rows else (0.0, 0.0, 0.0, 0.0)
    bbox = cast(tuple[float, float, float, float], first_cell)
    return max(bbox[1], bbox[3])


def find_table_cells(
    page: pdfplumber.page.Page,
) -> list[tuple[tuple[float, float, float, float], int, int]]:
    """Return table cell bboxes in row-major (top-to-bottom, left-to-right) order.

    pdfplumber orders rows bottom-to-top in PDF coordinates, so we reverse the row
    list to restore visual reading order (FR-203).  Multiple tables are sorted
    so that the visually highest table comes first.
    """
    tables = list(page.find_tables() or [])
    tables.sort(key=_table_visual_upper, reverse=True)
    cells: list[tuple[tuple[float, float, float, float], int, int]] = []
    for table in tables:
        rows = list(table.rows)
        rows.reverse()
        for row_index, row in enumerate(rows):
            for col_index, cell in enumerate(row.cells):
                cells.append((cast(tuple[float, float, float, float], cell), row_index, col_index))
    return cells


def text_from_table_cell(
    page: pdfplumber.page.Page,
    cell_bbox: tuple[float, float, float, float],
    page_number: int,
) -> str:
    """Extract the text inside a single table cell, preserving line order."""
    x0, top, x1, bottom = cell_bbox
    cell_upper = max(top, bottom)
    cell_lower = min(top, bottom)
    glyphs = [
        g
        for g in _glyphs_from_page(page, page_number)
        if g.x0 >= x0 - 0.5
        and g.x1 <= x1 + 0.5
        and max(g.top, g.bottom) <= cell_upper + 0.5
        and min(g.top, g.bottom) >= cell_lower - 0.5
    ]
    if not glyphs:
        return ""

    # Preserve line breaks if the cell contains multiple lines.
    # Visual top-to-bottom = descending visual upper boundary.
    glyphs.sort(key=lambda g: (-_visual_top(g), g.x0))
    line_gap = max(0.3 * _median_font_size(glyphs), 2.0)
    lines: list[list[Glyph]] = []
    current: list[Glyph] = []
    for glyph in glyphs:
        if not current:
            current.append(glyph)
            continue
        previous_upper = _visual_top(current[-1])
        current_upper = _visual_top(glyph)
        if previous_upper - current_upper > line_gap:
            lines.append(current)
            current = [glyph]
        else:
            current.append(glyph)
    if current:
        lines.append(current)

    return "\n".join(
        normalize_text(_build_line(line).text) for line in lines if _build_line(line).text
    )


def _median_font_size(glyphs: Sequence[Glyph]) -> float:
    sizes = sorted(g.font_size for g in glyphs if g.font_size > 0)
    if not sizes:
        return 12.0
    mid = len(sizes) // 2
    return sizes[mid] if len(sizes) % 2 else (sizes[mid - 1] + sizes[mid]) / 2
