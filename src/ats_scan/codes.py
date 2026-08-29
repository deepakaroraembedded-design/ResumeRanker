from __future__ import annotations

from enum import StrEnum


class ReasonCode(StrEnum):
    """Stable reason and flag identifiers used across the engine.

    Values are taken from TRD Appendix B.
    """

    # Ingest (S1)
    ING_UNSUPPORTED_TYPE = "ING_UNSUPPORTED_TYPE"
    ING_OVERSIZE = "ING_OVERSIZE"
    ING_EMPTY = "ING_EMPTY"
    ING_DUPLICATE = "ING_DUPLICATE"

    # Extraction (S2)
    EXT_ENCRYPTED = "EXT_ENCRYPTED"
    EXT_CORRUPT = "EXT_CORRUPT"
    EXT_OCR_LOW_CONFIDENCE = "EXT_OCR_LOW_CONFIDENCE"
    LANG_UNSUPPORTED = "LANG_UNSUPPORTED"

    # Structuring / scoring (S3)
    S3_DATE_AMBIGUOUS = "S3_DATE_AMBIGUOUS"
    MULTI_RESUME = "MULTI_RESUME"
    LLM_DEGRADED = "LLM_DEGRADED"
    DETERMINISTIC_MODE = "DETERMINISTIC_MODE"

    # Knockouts
    KO_UNVERIFIED = "KO_UNVERIFIED"

    # Integrity flags
    HIDDEN_TEXT = "HIDDEN_TEXT"
    KEYWORD_STUFFING = "KEYWORD_STUFFING"
    INJECTION_ATTEMPT = "INJECTION_ATTEMPT"

    # Confidence / review
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"

    @classmethod
    def all(cls) -> frozenset[str]:
        """Return all registered reason-code strings."""
        return frozenset(str(member) for member in cls)


def is_known(code: str) -> bool:
    """Return True if *code* is a registered reason code."""
    return code in ReasonCode.all()
