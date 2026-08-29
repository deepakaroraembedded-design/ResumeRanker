from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pymupdf as fitz
import pytest

from ats_scan.extract.pdf import PdfExtractor
from ats_scan.extract.pdf._config import PdfExtractionConfig
from ats_scan.models.run import RunContext
from ats_scan.models.source import SourceDocument

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _source(path: Path) -> SourceDocument:
    return SourceDocument(
        path=str(path),
        content_sha256="a" * 64,
        bytes=path.stat().st_size,
        mtime="2026-01-01T00:00:00",
        media_type="application/pdf",
    )


def _build_fixture(tmp_path: Path, name: str, layout: dict[str, Any]) -> tuple[Path, list[str]]:
    path = tmp_path / f"{name}.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    expected: list[str] = []
    if layout.get("two_column"):
        left = layout["left"]
        right = layout["right"]
        for i, line in enumerate(left):
            page.insert_text((50, 700 - i * 25), line, fontsize=10, color=(0, 0, 0))
        for i, line in enumerate(right):
            page.insert_text((300, 700 - i * 25), line, fontsize=10, color=(0, 0, 0))
        expected.extend(left)
        expected.extend(right)
    elif layout.get("table"):
        rows = layout["rows"]
        cell_width = layout.get("cell_width", 120)
        cell_height = layout.get("cell_height", 25)
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                x0 = 50 + c * cell_width
                y0 = 650 - r * cell_height
                y1 = y0 + cell_height
                page.insert_text(
                    (x0 + 5, y0 + cell_height - 5),
                    text,
                    fontsize=10,
                    color=(0, 0, 0),
                )
                page.draw_rect(fitz.Rect(x0, y0, x0 + cell_width, y1), color=(0, 0, 0))
        expected.extend([cell for row in rows for cell in row])
    else:
        for i, line in enumerate(layout["lines"]):
            page.insert_text((50, 700 - i * 25), line, fontsize=10, color=(0, 0, 0))
        expected.extend(layout["lines"])
    doc.save(path)
    doc.close()
    return path, expected


GOLDEN_CASES = [
    (
        "g_000_single_column_contact",
        {
            "lines": [
                "Ravi Menon",
                "ravi.menon@example.com",
                "+1 555 123 4567",
                "Summary",
                "Senior data engineer with cloud experience.",
            ]
        },
    ),
    (
        "g_001_single_column_experience",
        {
            "lines": [
                "Experience",
                "Acme Corp, Senior Data Engineer, 2020-2024",
                "Built PySpark pipelines on AWS.",
                "Globex, Data Engineer, 2017-2020",
                "Maintained PostgreSQL data warehouse.",
            ]
        },
    ),
    (
        "g_002_single_column_skills",
        {
            "lines": [
                "Skills",
                "Python, Spark, SQL, dbt, AWS, Terraform",
                "Certifications",
                "AWS Certified Solutions Architect",
            ]
        },
    ),
    (
        "g_003_two_column_resume",
        {
            "two_column": True,
            "left": ["Contact", "Ravi Menon", "Skills", "Python, SQL"],
            "right": ["Experience", "Acme 2020-2024", "Education", "MS CS"],
        },
    ),
    (
        "g_004_table_skills_matrix",
        {
            "table": True,
            "rows": [
                ["Skill", "Years", "Level"],
                ["Python", "8", "Expert"],
                ["Spark", "5", "Advanced"],
                ["dbt", "2", "Intermediate"],
            ],
        },
    ),
    (
        "g_005_single_column_projects",
        {
            "lines": [
                "Projects",
                "Data mesh ingestion pipeline",
                "Technologies: Kafka, Flink, PostgreSQL",
                "Outcome: 40% latency reduction",
            ]
        },
    ),
    (
        "g_006_single_column_education",
        {
            "lines": [
                "Education",
                "MS Computer Science, State University, 2016",
                "BS Computer Science, Tech College, 2014",
            ]
        },
    ),
    (
        "g_007_two_column_publications",
        {
            "two_column": True,
            "left": ["Publications", "Paper A on data lakes"],
            "right": ["Paper B on streaming", "Paper C on ML pipelines"],
        },
    ),
    (
        "g_008_table_experience_grid",
        {
            "table": True,
            "rows": [
                ["Employer", "Role", "Years"],
                ["Acme", "Data Engineer", "2020-2024"],
                ["Globex", "Engineer", "2017-2020"],
            ],
        },
    ),
    (
        "g_009_single_column_summary",
        {
            "lines": [
                "Summary",
                "Platform engineer with Kubernetes and Terraform expertise.",
                "Seeking senior infrastructure roles.",
            ]
        },
    ),
    (
        "g_010_mixed_layout",
        {
            "lines": [
                "Ravi Menon",
                "Summary: Cloud-first data engineer.",
                "Skills",
            ],
            "table": True,
            "rows": [
                ["Python", "8 years"],
                ["Spark", "5 years"],
            ],
        },
    ),
    (
        "g_011_single_column_certifications",
        {
            "lines": [
                "Certifications",
                "AWS Certified Solutions Architect",
                "Google Professional Data Engineer",
                "Databricks Data Engineer Associate",
            ]
        },
    ),
]


@pytest.mark.golden
@pytest.mark.parametrize(("name", "layout"), GOLDEN_CASES)
def test_golden_extraction(name: str, layout: dict[str, Any], tmp_path: Path) -> None:
    path, expected = _build_fixture(tmp_path, name, layout)
    extractor = PdfExtractor(PdfExtractionConfig(chars_per_page_threshold=10))
    source = _source(path)
    result = extractor.extract(source, RunContext(run_id="r1"))
    assert result.ok, result.diagnostics
    text = result.value.text
    for snippet in expected:
        assert snippet in text, f"{name}: missing {snippet!r}"
