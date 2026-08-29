from __future__ import annotations

from collections.abc import Mapping

from ats_scan.models.resume import CanonicalResume
from ats_scan.models.scoring import SubScore


def _extraction_quality(resume: CanonicalResume) -> float:
    """Return extraction quality in [0,1] per TRD §5.5.

    A native text layer scores 1.0. OCR-based extraction uses the reported OCR
    confidence. Quality is bounded to [0,1].
    """
    if resume.extraction is None:
        return 1.0
    if resume.extraction.ocr_confidence is not None:
        return max(0.0, min(1.0, resume.extraction.ocr_confidence))
    if resume.extraction.quality is not None:
        return max(0.0, min(1.0, resume.extraction.quality))
    return 1.0


def _evidence_density(sub_scores: Mapping[str, SubScore]) -> float:
    """Return evidence density in [0,1] per TRD §5.5.

    Counts distinct cited evidence spans across active sub-scores and divides by
    the number of active dimensions. The result is clipped to [0,1].
    """
    active = [sub for sub in sub_scores.values() if sub.value is not None]
    if not active:
        return 0.0

    distinct_spans: set[tuple[int, int, str, str]] = set()
    for sub in active:
        for ev in sub.evidence:
            span = ev.span
            if span and len(span) == 2:
                distinct_spans.add((span[0], span[1], ev.source, sub.dimension))

    return min(1.0, len(distinct_spans) / max(1, len(active)))


def _model_agreement(sub_scores: Mapping[str, SubScore], rubric_stdev: float | None) -> float:
    """Return model agreement in [0,1] per TRD §5.5."""
    if rubric_stdev is not None:
        return max(0.0, 1.0 - rubric_stdev / 25.0)

    s3 = sub_scores.get("S3")
    if s3 is not None and s3.detail:
        stdev = s3.detail.get("rubric_stdev")
        if isinstance(stdev, (int, float)):
            return max(0.0, 1.0 - float(stdev) / 25.0)
    return 1.0


def confidence(
    resume: CanonicalResume,
    sub_scores: Mapping[str, SubScore],
    mode: str,
    *,
    rubric_stdev: float | None = None,
) -> float:
    """Compute the confidence score in [0,1] per TRD §5.5.

    Formula::

        C = 0.30 * parse_completeness
          + 0.25 * extraction_quality
          + 0.25 * evidence_density
          + 0.20 * model_agreement

    ``model_agreement`` is 1.0 in deterministic/offline mode; in hybrid mode it
    is derived from ``rubric_stdev`` (or the ``rubric_stdev`` stored in S3's
    detail). Confidence below 0.60 is flagged ``LOW_CONFIDENCE`` by the caller,
    never used to exclude a candidate.
    """
    parse_completeness = max(0.0, min(1.0, resume.parse_completeness or 0.0))
    extraction_quality = _extraction_quality(resume)
    evidence_density = _evidence_density(sub_scores)

    model_agreement = _model_agreement(sub_scores, rubric_stdev) if mode == "hybrid" else 1.0

    c = (
        0.30 * parse_completeness
        + 0.25 * extraction_quality
        + 0.25 * evidence_density
        + 0.20 * model_agreement
    )
    return max(0.0, min(1.0, c))
