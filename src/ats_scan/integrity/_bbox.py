from __future__ import annotations

MediaBox = tuple[float, float, float, float]

DEFAULT_MEDIA_BOX: MediaBox = (0.0, 0.0, 1.0, 1.0)


def is_outside_media_box(
    bbox: tuple[float, float, float, float],
    media_box: MediaBox | None = None,
) -> bool:
    """Return True if *bbox* is entirely outside *media_box*.

    When *media_box* is not provided the unit square (0,0,1,1) is assumed, which
    matches normalised PDF page coordinates.  TRD §3.11 / FR-1101.
    """
    if media_box is None:
        x0, y0, x1, y1 = DEFAULT_MEDIA_BOX
    else:
        x0, y0, x1, y1 = media_box
    bx0, by0, bx1, by1 = bbox
    return bx1 <= x0 or bx0 >= x1 or by1 <= y0 or by0 >= y1
