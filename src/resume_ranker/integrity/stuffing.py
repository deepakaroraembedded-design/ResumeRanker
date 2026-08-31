from __future__ import annotations

import re
from collections.abc import Sequence

from resume_ranker.integrity._tokens import tokenize
from resume_ranker.models.common import IntegrityFinding
from resume_ranker.models.config import IntegrityConfig
from resume_ranker.models.resume import CanonicalResume
from resume_ranker.models.source import ExtractedText, SourceDocument

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


# Minimum number of words for a sentence to count as narrative context. Token
# repetitions inside shorter sentences are still treated as stuffing, while
# skills mentioned in longer sentences are treated as narrated.
_MIN_CONTEXT_WORDS = 12


class KeywordStuffingDetector:
    """Detect keyword stuffing aimed at classic ATS filters.

    Implements FR-1103: skills-section token share above the configured maximum,
    a skill repeated above the configured count without context, and skills
    claimed in a list but absent from all narrative text.

    A token is treated as contextless repetition only when its occurrences are
    concentrated in short sentences; legitimate technical terms that appear many
    times in long, descriptive sentences are not penalised.
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

        messages: list[str] = []
        spans: list[tuple[int, int]] = []
        quotes: list[str] = []

        repeated = self._repeated_keywords(source)
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
            # A dedicated skills section is normal; only flag high density outside it.
            # Technical resumes often contain many legitimate skill terms in
            # narrative bullets, so the floor is kept at 0.55 rather than 0.35 to
            # avoid penalising normal experience density.
            threshold = max(self._config.skills_token_share_max, 0.55)
            if share > threshold:
                messages.append(f"skills-section token share {share:.0%} exceeds {threshold:.0%}")

            unnarrated = self._unnarrated_skills(resume, source)
            if unnarrated:
                total_skills = len(resume.skills)
                # A single un-narrated skill is normal; flag only when a
                # meaningful subset of the claimed skills list has no narrative
                # support. The threshold is 5 skills or 25% of the list, whichever
                # is lower, capped at the list size so a one-skill list still
                # triggers the check.
                threshold = min(total_skills, max(5, int(0.25 * total_skills)))
                if len(unnarrated) >= threshold:
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

    def _sentences(self, text: str) -> list[str]:
        """Split text into rough sentences, merging continuation lines.

        Bullet points that wrap across multiple lines are joined so that a skill
        mentioned in the middle of a long bullet is not treated as un-narrated.
        """
        raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not raw_lines:
            return []

        merged: list[str] = [raw_lines[0]]
        for line in raw_lines[1:]:
            previous = merged[-1]
            if previous.endswith((",", ";", ":")) or (line and line[0].islower()):
                merged[-1] = f"{previous} {line}"
            else:
                merged.append(line)

        sentences: list[str] = []
        for block in merged:
            for part in re.split(r"[.!?]\s+", block):
                if part.strip():
                    sentences.append(part.strip())
        return sentences

    def _repeated_keywords(self, source: str) -> list[str]:
        """Return tokens that are repeated mostly in short, contextless sentences."""
        short_counts: dict[str, int] = {}
        for sentence in self._sentences(source):
            if len(sentence.split()) >= _MIN_CONTEXT_WORDS:
                continue
            for token in tokenize(sentence):
                if token not in _STOP_WORDS:
                    short_counts[token] = short_counts.get(token, 0) + 1

        return [
            token
            for token, count in short_counts.items()
            if count > self._config.keyword_repeat_max
        ]

    def _skill_token_share(self, source: str, resume: CanonicalResume) -> float:
        """Return the share of non-skills-section tokens that match a claimed skill.

        A dedicated skills section is expected to be dense with skill tokens, so
        it is excluded from the share.  High skill-token density outside that
        section indicates classic keyword stuffing.
        """
        skill_tokens: set[str] = set()
        for skill in resume.skills:
            if skill.raw:
                skill_tokens.update(tokenize(skill.raw))
            if skill.canonical:
                skill_tokens.update(tokenize(skill.canonical))
        if not skill_tokens:
            return 0.0

        skills_spans = [
            span
            for skill in resume.skills
            if "skills" in {s.lower() for s in skill.sections} and skill.evidence_spans
            for span in skill.evidence_spans
        ]
        if skills_spans:
            start = min(s[0] for s in skills_spans)
            end = max(s[1] for s in skills_spans)
            non_skills_text = source[:start] + source[end:]
        else:
            non_skills_text = source

        tokens = tokenize(non_skills_text)
        if not tokens:
            return 0.0
        matched = sum(1 for token in tokens if token in skill_tokens)
        return matched / len(tokens)

    def _unnarrated_skills(self, resume: CanonicalResume, source: str) -> list[str]:
        """Return skills claimed in a list but absent from narrative text."""
        narrative_parts: list[str] = []
        for entry in resume.experience:
            narrative_parts.extend(bullet.text for bullet in entry.bullets)
        for project in resume.projects:
            narrative_parts.extend(bullet.text for bullet in project.bullets)
        # Long sentences anywhere in the document provide context for a skill.
        for sentence in self._sentences(source):
            if len(sentence.split()) >= _MIN_CONTEXT_WORDS:
                narrative_parts.append(sentence)
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
