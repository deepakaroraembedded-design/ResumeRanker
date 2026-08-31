from __future__ import annotations

from tests.unit.integrity.conftest import extracted_text, source_doc

from resume_ranker.integrity.stuffing import KeywordStuffingDetector
from resume_ranker.models.config import IntegrityConfig
from resume_ranker.models.resume import (
    Bullet,
    CanonicalResume,
    ExperienceEntry,
    SkillMention,
)
from resume_ranker.models.source import ExtractedText


def _plain_text(text: str) -> ExtractedText:
    return ExtractedText(
        text=text,
        metadata=extracted_text().metadata,
        blocks=(),
    )


def test_repeated_skill_without_context_raises() -> None:
    """A token repeated more than keyword_repeat_max times is stuffing."""
    text = _plain_text(" ".join(["Python"] * 10))
    findings = KeywordStuffingDetector().inspect(source_doc(), text, None)
    assert len(findings) == 1
    assert findings[0].code == "KEYWORD_STUFFING"
    assert "python" in findings[0].message.lower()


def test_no_repetition_is_clean() -> None:
    """Normal skill mentions do not trigger repetition."""
    text = _plain_text("Python Java JavaScript React Node.js")
    findings = KeywordStuffingDetector().inspect(source_doc(), text, None)
    assert not findings


def test_skills_section_token_share_raises() -> None:
    """A high share of skill tokens in the text raises KEYWORD_STUFFING."""
    config = IntegrityConfig(keyword_repeat_max=100)  # disable repetition path
    resume = CanonicalResume(
        candidate_id="c1",
        skills=[SkillMention(raw="Python")],
    )
    text = _plain_text("Python Python Python Python Python Python other")
    findings = KeywordStuffingDetector(config).inspect(source_doc(), text, resume)
    assert len(findings) == 1
    assert findings[0].code == "KEYWORD_STUFFING"


def test_claimed_but_unnarrated_skill_raises() -> None:
    """A skill claimed in a list but absent from narrative text is flagged."""
    config = IntegrityConfig(
        keyword_repeat_max=100, skills_token_share_max=1.0
    )  # disable the other two paths
    resume = CanonicalResume(
        candidate_id="c1",
        skills=[SkillMention(raw="Kubernetes")],
        experience=(
            ExperienceEntry(
                employer="Acme",
                title="Engineer",
                bullets=(Bullet(text="Used Python daily."),),
            ),
        ),
    )
    text = _plain_text("Skills: Kubernetes")
    findings = KeywordStuffingDetector(config).inspect(source_doc(), text, resume)
    assert len(findings) == 1
    assert "kubernetes" in findings[0].message.lower()


def test_narrated_skill_is_clean() -> None:
    """A claimed skill that appears in narrative text is not stuffing."""
    config = IntegrityConfig(keyword_repeat_max=100, skills_token_share_max=1.0)
    resume = CanonicalResume(
        candidate_id="c1",
        skills=[SkillMention(raw="Python")],
        experience=(
            ExperienceEntry(
                employer="Acme",
                title="Engineer",
                bullets=(Bullet(text="Used Python daily."),),
            ),
        ),
    )
    text = _plain_text("Skills: Python")
    findings = KeywordStuffingDetector(config).inspect(source_doc(), text, resume)
    assert not findings


def test_empty_text_is_clean() -> None:
    """An empty text produces no findings."""
    text = _plain_text("")
    findings = KeywordStuffingDetector().inspect(source_doc(), text, None)
    assert not findings
