from __future__ import annotations

import re
from collections.abc import Sequence

from ats_scan.models.common import IntegrityFinding
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.source import ExtractedText, SourceDocument

# Instruction-like patterns directed at a language model.  Kept conservative to
# avoid false positives on legitimate resume language while still catching the
# adversarial strings described in TRD §3.11 / FR-1104 and §6.4.
_INJECTION_PATTERNS: tuple[str, ...] = (
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"ignore\s+(?:all\s+|the\s+|previous\s+)?instructions",
    r"ignore\s+the\s+above",
    r"disregard\s+(?:all\s+|previous\s+|the\s+)?instructions",
    r"disregard\s+the\s+above",
    r"forget\s+(?:all\s+|previous\s+|the\s+)?instructions",
    r"rate\s+this\s+(?:candidate|resume|applicant)(?:\s+as\s+[^.]+)?",
    r"rank\s+this\s+(?:candidate|resume|applicant)(?:\s+as\s+[^.]+)?",
    r"score\s+this\s+(?:candidate|resume|applicant)(?:\s+as\s+[^.]+)?",
    r"select\s+this\s+(?:candidate|resume|applicant)",
    r"give\s+(?:this|the)\s+(?:candidate|resume|applicant)\s+(?:a\s+)?(?:high|top|perfect|excellent)[^.]*",
    r"you\s+are\s+(?:now\s+)?(?:a\s+)?(?:recruiter|hiring|reviewer|evaluator|model|ai|llm)",
    r"from\s+now\s+on\s+(?:you\s+are|the\s+model|the\s+system|this\s+ai)",
    r"treat\s+(?:this|the)\s+(?:candidate|resume)\s+as(?:\s+an?\s+[^.]+)?",
    r"do\s+not\s+(?:ignore|disregard|score|evaluate|read|process|reject)[^.]*",
)

_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


class InjectionDetector:
    """Detect instruction-like content directed at a language model.

    Implements FR-1104.  Findings carry the exact character spans that must be
    quarantined from model prompts (FR-1105 / TRD §6.4).
    """

    code = "INJECTION_ATTEMPT"

    def inspect(
        self,
        doc: SourceDocument,
        text: ExtractedText,
        resume: CanonicalResume | None,
    ) -> Sequence[IntegrityFinding]:
        """Return findings for prompt-injection-like content in *text*."""
        source = text.text
        spans: list[tuple[int, int]] = []
        quotes: list[str] = []
        for match in _INJECTION_RE.finditer(source):
            spans.append(match.span())
            quotes.append(source[match.start() : match.end()])

        if not spans:
            return ()

        return (
            IntegrityFinding(
                detector=self.__class__.__name__,
                code=self.code,
                message=(
                    f"Prompt injection detected: {len(spans)} instruction-like "
                    "span(s) directed at a language model"
                ),
                spans=tuple(spans),
                quotes=tuple(quotes),
            ),
        )
