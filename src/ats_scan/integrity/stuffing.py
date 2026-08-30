from __future__ import annotations

import re
from collections.abc import Sequence

from ats_scan.integrity._tokens import tokenize
from ats_scan.models.common import IntegrityFinding
from ats_scan.models.config import IntegrityConfig
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.source import ExtractedText, SourceDocument

# Common English function words that should not count as keyword stuffing.
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "for",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "can",
        "shall",
        "this",
        "that",
        "these",
        "those",
        "i",
        "me",
        "my",
        "myself",
        "we",
        "our",
        "ours",
        "you",
        "your",
        "yours",
        "he",
        "him",
        "his",
        "she",
        "her",
        "it",
        "its",
        "they",
        "them",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "where",
        "when",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "now",
    }
)


class KeywordStuffingDetector:
    """Detect keyword stuffing aimed at classic ATS filters.

    Implements FR-1103: skills-section token share above the configured maximum,
    a skill repeated above the configured count without context, and skills
    claimed in a list but absent from all narrative text.
    """

    code = "KEYWORD_STUFFING"

    def __init__(self, config: IntegrityConfig | None = None) -> None:
        self._config = IntegrityConfig() if config is None else config

    def inspect(
        self,
        doc: SourceDocument,
        text: ExtractedText,
        resume: CanonicalResume | None,
    ) -> Sequence[IntegrityFinding]:
        """Return findings for keyword stuffing in *text*."""
        source = text.text
        tokens = tokenize(source)
        if not tokens:
            return ()

        counts: dict[str, int] = {}
        for token in tokens:
            if token not in _STOP_WORDS:
                counts[token] = counts.get(token, 0) + 1

        messages: list[str] = []
        spans: list[tuple[int, int]] = []
        quotes: list[str] = []

        repeated = [
            token for token, count in counts.items() if count > self._config.keyword_repeat_max
        ]
        if repeated:
            messages.append(
                f"repeated keywords exceeding {self._config.keyword_repeat_max}: "
                f"{', '.join(repeated)}"
            )
            for token in repeated:
                for match in re.finditer(rf"\b{re.escape(token)}\b", source, re.IGNORECASE):
                    spans.append(match.span())
                    quotes.append(source[match.start() : match.end()])

        if resume is not None:
            share = self._skill_token_share(source, resume)
            if share > self._config.skills_token_share_max:
                messages.append(
                    f"skills-section token share {share:.0%} exceeds "
                    f"{self._config.skills_token_share_max:.0%}"
                )

            unnarrated = self._unnarrated_skills(resume)
            if unnarrated:
                messages.append(f"claimed-but-unnarrated skills: {', '.join(unnarrated)}")

        if not messages:
            return ()

        return (
            IntegrityFinding(
                detector=self.__class__.__name__,
                code=self.code,
                message="Keyword stuffing detected: " + "; ".join(messages),
                spans=tuple(spans),
                quotes=tuple(quotes),
            ),
        )

    def _skill_token_share(self, source: str, resume: CanonicalResume) -> float:
        """Return the share of tokens in *source* that match a claimed skill."""
        skill_tokens: set[str] = set()
        for skill in resume.skills:
            if skill.raw:
                skill_tokens.update(tokenize(skill.raw))
            if skill.canonical:
                skill_tokens.update(tokenize(skill.canonical))
        if not skill_tokens:
            return 0.0
        tokens = tokenize(source)
        if not tokens:
            return 0.0
        matched = sum(1 for token in tokens if token in skill_tokens)
        return matched / len(tokens)

    def _unnarrated_skills(self, resume: CanonicalResume) -> list[str]:
        """Return skills claimed in a list but absent from narrative text."""
        narrative_parts: list[str] = []
        for entry in resume.experience:
            narrative_parts.extend(bullet.text for bullet in entry.bullets)
        for project in resume.projects:
            narrative_parts.extend(bullet.text for bullet in project.bullets)
        narrative = " ".join(narrative_parts).lower()

        unnarrated: list[str] = []
        for skill in resume.skills:
            names: set[str] = set()
            if skill.raw:
                names.update(tokenize(skill.raw))
            if skill.canonical:
                names.update(tokenize(skill.canonical))
            if names and not any(name in narrative for name in names):
                unnarrated.append(skill.raw or skill.canonical or "unknown")
        return unnarrated
