from __future__ import annotations

from collections.abc import Sequence

from resume_ranker.integrity._bbox import is_outside_media_box
from resume_ranker.integrity._colour import delta_e_rgb
from resume_ranker.integrity._offset import build_text
from resume_ranker.integrity._tokens import tokenize
from resume_ranker.models.common import IntegrityFinding
from resume_ranker.models.config import IntegrityConfig
from resume_ranker.models.resume import CanonicalResume
from resume_ranker.models.source import ExtractedText, SourceDocument, TextBlock

_WHITE: tuple[float, float, float] = (1.0, 1.0, 1.0)


class HiddenTextDetector:
    """Detect text that is present in the file but not visible to a human reader.

    Implements FR-1101 (glyph-level hidden-text cues: colour near the page
    background, font size below the configured minimum, render mode 3, and text
    outside the media box) and FR-1102 (text-layer / visible-token
    corroboration: the hidden-token share must exceed the configured threshold
    before a finding is raised).
    """

    code = "HIDDEN_TEXT"

    def __init__(self, config: IntegrityConfig | None = None) -> None:
        self._config = IntegrityConfig() if config is None else config

    def inspect(
        self,
        doc: SourceDocument,
        text: ExtractedText,
        resume: CanonicalResume | None,
    ) -> Sequence[IntegrityFinding]:
        """Return findings for hidden text in *text*."""
        blocks = text.blocks
        if not blocks:
            return ()

        source_text, block_spans = build_text(blocks)
        if not source_text:
            return ()

        total_tokens = 0
        hidden_tokens = 0
        hidden_spans: list[tuple[int, int]] = []
        hidden_quotes: list[str] = []

        for block, span in zip(blocks, block_spans, strict=False):
            block_tokens = tokenize(block.text)
            total_tokens += len(block_tokens)
            if self._is_hidden(block):
                hidden_tokens += len(block_tokens)
                hidden_spans.append(span)
                hidden_quotes.append(source_text[span[0] : span[1]])

        if total_tokens == 0 or hidden_tokens == 0:
            return ()

        share = hidden_tokens / total_tokens
        if share <= self._config.hidden_text_token_delta_share:
            return ()

        return (
            IntegrityFinding(
                detector=self.__class__.__name__,
                code=self.code,
                message=(
                    f"Hidden text detected: {hidden_tokens} of {total_tokens} "
                    f"tokens ({share:.0%}) exceed the configured threshold "
                    f"({self._config.hidden_text_token_delta_share:.0%})"
                ),
                spans=tuple(hidden_spans),
                quotes=tuple(hidden_quotes),
            ),
        )

    def _is_hidden(self, block: TextBlock) -> bool:
        """Return True when a glyph block exhibits a hidden-text cue."""
        if block.render_mode == 3:
            return True
        if block.font_size is not None and block.font_size < self._config.min_font_pt:
            return True
        if block.colour is not None and delta_e_rgb(block.colour, _WHITE) < 5.0:
            return True
        return is_outside_media_box(block.bbox)
