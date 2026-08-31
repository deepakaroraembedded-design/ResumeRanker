from __future__ import annotations

from typing import Any

import pytest

from resume_ranker.models.common import StageResult
from resume_ranker.models.llm import LLMResult
from resume_ranker.models.resume import DateValue
from resume_ranker.models.run import RunContext
from resume_ranker.models.source import ExtractedText, ExtractionMetadata
from resume_ranker.protocols import LLMClient, Structurer
from resume_ranker.structure.llm_parse import (
    HeuristicStructurer,
    HybridStructurer,
    _LLMCertification,
    _LLMEducationEntry,
    _LLMExperienceEntry,
    _LLMResponse,
    _LLMResumeOutput,
)


class TestHeuristicStructurer:
    """Tests for the deterministic heuristic structurer."""

    @pytest.fixture
    def sample_text(self) -> ExtractedText:
        return ExtractedText(
            text="""\
Jane Doe
jane.doe@example.com

Experience
Acme Corp | Senior Software Engineer | 2020 – 2024
- Led Python migration.

Education
BS in Computer Science, University of Example, 2016

Skills
Python, AWS, Docker
""",
            metadata=ExtractionMetadata(method="test"),
        )

    @pytest.fixture
    def ctx(self) -> RunContext:
        return RunContext(run_id="r1", now="2026-08-29")

    def test_implements_protocol(self, sample_text: ExtractedText, ctx: RunContext) -> None:
        structurer = HeuristicStructurer()
        assert isinstance(structurer, Structurer)
        result = structurer.structure(sample_text, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        assert resume.candidate_id == "c_unknown"
        assert resume.identity is not None
        assert resume.identity.full_name == "Jane Doe"
        assert resume.identity.emails == ("jane.doe@example.com",)
        assert len(resume.experience) == 1
        assert resume.experience[0].employer == "Acme Corp"
        assert resume.timeline is not None
        assert resume.timeline.total_months_covered is not None
        assert resume.parse_completeness is not None

    def test_no_fabrication(self, ctx: RunContext) -> None:
        text = ExtractedText(
            text="Jane Doe\n\nSome unrelated text.",
            metadata=ExtractionMetadata(method="test"),
        )
        structurer = HeuristicStructurer()
        result = structurer.structure(text, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        assert resume.experience == ()
        assert resume.education == ()
        assert resume.skills == ()


class TestHybridStructurer:
    """Tests for the hybrid structurer with LLM fallback."""

    @pytest.fixture
    def sample_text(self) -> ExtractedText:
        return ExtractedText(
            text="""\
Jane Doe
jane.doe@example.com

Experience
Acme Corp | Senior Software Engineer | 2020 – 2024
- Led Python migration.

Education
BS in Computer Science, University of Example, 2016

Skills
Python, AWS, Docker
""",
            metadata=ExtractionMetadata(method="test"),
        )

    @pytest.fixture
    def ctx(self) -> RunContext:
        return RunContext(run_id="r1", now="2026-08-29")

    def test_offline_mode_uses_heuristic(self, sample_text: ExtractedText, ctx: RunContext) -> None:
        structurer = HybridStructurer(llm=None)
        result = structurer.structure(sample_text, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        assert resume.identity is not None
        assert resume.identity.full_name == "Jane Doe"

    def test_bad_llm_falls_back_with_degraded(
        self, sample_text: ExtractedText, ctx: RunContext
    ) -> None:
        class BadLLM(LLMClient):
            async def structured(self, **kwargs: Any) -> StageResult[Any]:
                return StageResult(value=None)

        structurer = HybridStructurer(llm=BadLLM())
        result = structurer.structure(sample_text, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        codes = [d["code"] for d in resume.diagnostics]
        assert "LLM_DEGRADED" in codes

    def test_schema_mismatch_falls_back(self, sample_text: ExtractedText, ctx: RunContext) -> None:
        from tests.fakes import FakeLLMClient

        structurer = HybridStructurer(llm=FakeLLMClient())
        result = structurer.structure(sample_text, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        codes = [d["code"] for d in resume.diagnostics]
        assert "LLM_DEGRADED" in codes

    def test_good_llm_returns_structured(self, sample_text: ExtractedText, ctx: RunContext) -> None:
        text = sample_text.text
        name_pos = text.find("Jane Doe")
        email_pos = text.find("jane.doe@example.com")
        employer_pos = text.find("Acme Corp")
        title_pos = text.find("Senior Software Engineer")
        exp = _LLMExperienceEntry(
            employer="Acme Corp",
            employer_span=(employer_pos, employer_pos + len("Acme Corp")),
            title="Senior Software Engineer",
            title_span=(title_pos, title_pos + len("Senior Software Engineer")),
            start_date="2020-01-01",
            end_date="2024-01-01",
            bullets=["Led Python migration."],
        )
        llm_resume = _LLMResumeOutput(
            full_name="Jane Doe",
            full_name_span=(name_pos, name_pos + len("Jane Doe")),
            email="jane.doe@example.com",
            email_span=(email_pos, email_pos + len("jane.doe@example.com")),
            experience=[exp],
        )
        llm_response = _LLMResponse(resume=llm_resume)

        class GoodLLM(LLMClient):
            async def structured(self, **kwargs: Any) -> StageResult[LLMResult[Any]]:
                return StageResult(value=LLMResult(samples=(llm_response,)))

        structurer = HybridStructurer(llm=GoodLLM())
        result = structurer.structure(sample_text, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        assert resume.identity is not None
        assert resume.identity.full_name == "Jane Doe"
        assert resume.identity.emails == ("jane.doe@example.com",)
        assert resume.experience[0].employer == "Acme Corp"

    def test_llm_exception_falls_back(self, sample_text: ExtractedText, ctx: RunContext) -> None:
        class RaisingLLM(LLMClient):
            async def structured(self, **kwargs: Any) -> StageResult[LLMResult[Any]]:
                raise RuntimeError("boom")

        structurer = HybridStructurer(llm=RaisingLLM())
        result = structurer.structure(sample_text, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        codes = [d["code"] for d in resume.diagnostics]
        assert "LLM_DEGRADED" in codes

    def test_llm_returns_none_falls_back(self, sample_text: ExtractedText, ctx: RunContext) -> None:
        class NoneLLM(LLMClient):
            async def structured(self, **kwargs: Any) -> StageResult[LLMResult[Any]]:
                return StageResult(value=LLMResult(samples=()))

        structurer = HybridStructurer(llm=NoneLLM())
        result = structurer.structure(sample_text, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        codes = [d["code"] for d in resume.diagnostics]
        assert "LLM_DEGRADED" in codes

    def test_unverified_spans_are_dropped(
        self, sample_text: ExtractedText, ctx: RunContext
    ) -> None:
        llm_resume = _LLMResumeOutput(
            full_name="Jane Doe",
            full_name_span=(0, 0),  # invalid span
            email="jane.doe@example.com",
            email_span=(9999, 99999),  # invalid span
            experience=[],
        )
        llm_response = _LLMResponse(resume=llm_resume)

        class GoodLLM(LLMClient):
            async def structured(self, **kwargs: Any) -> StageResult[LLMResult[Any]]:
                return StageResult(value=LLMResult(samples=(llm_response,)))

        structurer = HybridStructurer(llm=GoodLLM())
        result = structurer.structure(sample_text, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        assert resume.identity is None or resume.identity.full_name is None

    def test_llm_education_and_certifications(self, ctx: RunContext) -> None:
        text = """\
Jane Doe
University of Example
AWS Cert
"""
        extracted = ExtractedText(text=text, metadata=ExtractionMetadata(method="test"))
        uni_pos = text.find("University of Example")
        cert_pos = text.find("AWS Cert")
        llm_resume = _LLMResumeOutput(
            full_name="Jane Doe",
            full_name_span=(0, len("Jane Doe")),
            education=[
                _LLMEducationEntry(
                    institution="University of Example",
                    institution_span=(uni_pos, uni_pos + len("University of Example")),
                    degree_level="BS",
                    graduation_date="2016",
                )
            ],
            certifications=[
                _LLMCertification(
                    name="AWS Cert",
                    name_span=(cert_pos, cert_pos + len("AWS Cert")),
                    issued="2020",
                )
            ],
        )
        llm_response = _LLMResponse(resume=llm_resume)

        class GoodLLM(LLMClient):
            async def structured(self, **kwargs: Any) -> StageResult[LLMResult[Any]]:
                return StageResult(value=LLMResult(samples=(llm_response,)))

        structurer = HybridStructurer(llm=GoodLLM())
        result = structurer.structure(extracted, ctx)
        assert result.ok
        resume = result.value
        assert resume is not None
        assert len(resume.education) == 1
        assert resume.education[0].institution == "University of Example"
        assert len(resume.certifications) == 1
        assert resume.certifications[0].name == "AWS Cert"


def date_value(value: str) -> Any:
    return DateValue(value=value)
