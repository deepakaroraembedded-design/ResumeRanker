from __future__ import annotations

from resume_ranker.models.config import BandConfig
from resume_ranker.models.scoring import Band


def band(composite: float, cfg: BandConfig) -> Band:
    """Return the band label for a composite score per TRD §5.4.

    Boundaries are read from *cfg*. The upper bound is inclusive; the lower
    bound is the next threshold down.
    """
    if composite >= cfg.strong:
        return Band.STRONG
    if composite >= cfg.good:
        return Band.GOOD
    if composite >= cfg.borderline:
        return Band.BORDERLINE
    if composite >= cfg.weak:
        return Band.WEAK
    return Band.NOT_A_MATCH
