from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ats_scan.models.common import StageResult
from ats_scan.models.llm import LLMResult
from ats_scan.models.resume import DateValue
from ats_scan.models.run import RunContext
from ats_scan.models.source import ExtractedText, ExtractionMetadata
from ats_scan.protocols import LLMClient
from ats_scan.structure import HeuristicStructurer, HybridStructurer
from ats_scan.structure.llm_parse import (
    _LLMExperienceEntry,
    _LLMResponse,
    _LLMResumeOutput,
)

CORPUS_DIR = Path(__file__).parents[2] / "corpus" / "resumes" / "synthetic"


def _load_resume_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extracted(text: str) -> ExtractedText:
    return ExtractedText(text=text, metadata=ExtractionMetadata(method="golden"))


def _ctx() -> RunContext:
    return RunContext(run_id="golden", now="2026-08-29")


def _f1_score(expected: set[str], actual: set[str]) -> float:
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    tp = len(expected & actual)
    precision = tp / len(actual) if actual else 0.0
    recall = tp / len(expected) if expected else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _field_set_for_resume(resume: Any) -> set[str]:
    fields: set[str] = set()
    if resume.identity and resume.identity.full_name:
        fields.add(f"name:{resume.identity.full_name}")
    for exp in resume.experience:
        if exp.employer:
            fields.add(f"employer:{exp.employer}")
        if exp.title_raw:
            fields.add(f"title:{exp.title_raw}")
        if exp.start and exp.start.value:
            fields.add(f"start:{exp.start.value}")
    for edu in resume.education:
        if edu.institution:
            fields.add(f"institution:{edu.institution}")
    for skill in resume.skills:
        fields.add(f"skill:{skill.raw.lower()}")
    return fields


class TestHeuristicGolden:
    """Golden-field accuracy for the heuristic structurer."""

    @pytest.mark.golden
    def test_heuristic_f1_on_synthetic_corpus(self) -> None:
        if not CORPUS_DIR.exists():
            pytest.skip("Synthetic corpus not available")
        paths = list(CORPUS_DIR.glob("*.md"))[:10]
        if not paths:
            pytest.skip("No synthetic resumes found")

        f1_scores: list[float] = []
        for path in paths:
            text = _load_resume_text(path)
            extracted = _extracted(text)
            structurer = HeuristicStructurer()
            result = structurer.structure(extracted, _ctx())
            assert result.ok, f"structuring failed for {path.name}"
            resume = result.value
            assert resume is not None

            expected = self._expected_fields(text)
            actual = _field_set_for_resume(resume)
            f1_scores.append(_f1_score(expected, actual))

        mean_f1 = sum(f1_scores) / len(f1_scores)
        assert mean_f1 >= 0.88, f"heuristic F1 {mean_f1} below threshold"

    def _expected_fields(self, text: str) -> set[str]:
        expected: set[str] = set()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            expected.add(f"name:{lines[0]}")
        # Employer and title appear on the first experience line.
        for line in lines:
            if "|" in line:
                parts = [part.strip() for part in line.split("|")]
                if len(parts) >= 2:
                    expected.add(f"employer:{parts[0]}")
                    expected.add(f"title:{parts[1]}")
                if len(parts) >= 3:
                    start_year = parts[2].split("–")[0].strip()
                    parsed = DateValue(value=f"{start_year}-01-01")
                    expected.add(f"start:{parsed.value}")
        # Education line has the year at the end.
        for line in lines:
            if line.startswith("BS"):
                parts = [part.strip() for part in line.split(",")]
                if len(parts) >= 2:
                    expected.add(f"institution:{parts[1]}")
        # Skills line is the comma-separated list near the top.
        for line in lines:
            if "," in line and "|" not in line and not line.startswith("BS"):
                for token in line.split(","):
                    token = token.strip().lower()
                    if token:
                        expected.add(f"skill:{token}")
        return expected


class TestHybridGolden:
    """Golden-field accuracy for the hybrid structurer with a fake LLM."""

    @pytest.mark.golden
    def test_hybrid_f1_with_perfect_llm(self) -> None:
        text = """\
Jane Doe
jane.doe@example.com

Experience
Acme Corp | Senior Software Engineer | 2020 – 2024
- Led Python migration.

Education
BS in Computer Science, University of Example, 2016

Skills
Python, AWS, Docker
"""
        extracted = _extracted(text)
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

        class PerfectLLM(LLMClient):
            async def structured(self, **kwargs: Any) -> StageResult[LLMResult[Any]]:
                return StageResult(value=LLMResult(samples=(llm_response,)))

        structurer = HybridStructurer(llm=PerfectLLM())
        result = structurer.structure(extracted, _ctx())
        assert result.ok
        resume = result.value
        assert resume is not None
        assert resume.identity is not None
        assert resume.identity.full_name == "Jane Doe"
        assert resume.experience[0].employer == "Acme Corp"
