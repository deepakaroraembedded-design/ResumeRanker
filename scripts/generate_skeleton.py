#!/usr/bin/env python3
"""Generate Wave 0 repository skeleton and stubs for RESUME-RANKER."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STUB_BODY = '''from __future__ import annotations

raise NotImplementedError("implemented by component agent")
'''

TEST_STUB_BODY = '''from __future__ import annotations


def test_stub() -> None:
    """Placeholder test; component agent replaces with real tests."""
    pass
'''

CONFTEXT_STUB_BODY = '''from __future__ import annotations


# Component-specific fixtures live here.
'''

DIRS = [
    # Source packages
    "src/resume_ranker",
    "src/resume_ranker/models",
    "src/resume_ranker/extract",
    "src/resume_ranker/extract/pdf",
    "src/resume_ranker/extract/ocr",
    "src/resume_ranker/extract/office",
    "src/resume_ranker/extract/plain",
    "src/resume_ranker/ingest",
    "src/resume_ranker/ontology",
    "src/resume_ranker/llm",
    "src/resume_ranker/llm/prompts",
    "src/resume_ranker/llm/schemas",
    "src/resume_ranker/integrity",
    "src/resume_ranker/report",
    "src/resume_ranker/structure",
    "src/resume_ranker/jobspec",
    "src/resume_ranker/embeddings",
    "src/resume_ranker/scoring",
    "src/resume_ranker/scoring/dimensions",
    "src/resume_ranker/fairness",
    "src/resume_ranker/config",
    "src/resume_ranker/cli",

    # Tests
    "tests",
    "tests/fakes",
    "tests/corpus/resumes/synthetic",
    "tests/corpus/resumes/adversarial",
    "tests/corpus/jobspecs",
    "tests/unit/ingest",
    "tests/unit/extract_pdf",
    "tests/unit/extract_office",
    "tests/unit/ontology",
    "tests/unit/llm",
    "tests/unit/integrity",
    "tests/unit/report",
    "tests/unit/structure",
    "tests/unit/jobspec",
    "tests/unit/scoring_evidence",
    "tests/unit/scoring_semantic",
    "tests/unit/scoring_profile",
    "tests/unit/scoring_aggregate",
    "tests/property",
    "tests/golden/structure",
    "tests/adversarial",
    "tests/fairness",
    "tests/integration",
    "tests/e2e",
    "tests/benchmark",
    "tests/qa",
    "tests/qa/corpus/gold",
    "tests/qa/corpus/adversarial",
    "tests/qa/corpus/edge",
    "tests/qa/corpus/fairness",
    "tests/qa/corpus/perf",
    "tests/qa/oracle",
    "tests/qa/regression",

    # Docs
    "docs/contracts",
    "docs/dep-requests",
    "docs/contract-change",
    "docs/qa",
    "docs/qa/defects",

    # Data
    "data/ontology/2026.07",
    "data/titles/2026.07",

    # Scripts
    "scripts/qa",

    # opencode
    ".opencode/commands",
    ".opencode/prompts",

    # changelog
    "changelog.d",
]

# Source module stubs owned by component agents (will be overwritten by W0 where needed).
STUB_MODULES = {
    # C-01
    "src/resume_ranker/ingest/__init__.py": None,
    "src/resume_ranker/ingest/manifest.py": None,
    # C-02
    "src/resume_ranker/extract/pdf/__init__.py": None,
    "src/resume_ranker/extract/pdf/extractor.py": None,
    "src/resume_ranker/extract/ocr/__init__.py": None,
    "src/resume_ranker/extract/ocr/extractor.py": None,
    # C-03
    "src/resume_ranker/extract/office/__init__.py": None,
    "src/resume_ranker/extract/office/extractor.py": None,
    "src/resume_ranker/extract/plain/__init__.py": None,
    "src/resume_ranker/extract/plain/extractor.py": None,
    # C-04
    "src/resume_ranker/ontology/__init__.py": None,
    "src/resume_ranker/ontology/loader.py": None,
    "src/resume_ranker/ontology/match.py": None,
    "src/resume_ranker/ontology/titles.py": None,
    # C-05
    "src/resume_ranker/llm/__init__.py": None,
    "src/resume_ranker/llm/adapter.py": None,
    "src/resume_ranker/llm/cache.py": None,
    "src/resume_ranker/llm/budget.py": None,
    # C-06
    "src/resume_ranker/integrity/__init__.py": None,
    "src/resume_ranker/integrity/hidden_text.py": None,
    "src/resume_ranker/integrity/stuffing.py": None,
    "src/resume_ranker/integrity/injection.py": None,
    # C-07
    "src/resume_ranker/report/__init__.py": None,
    "src/resume_ranker/report/csv.py": None,
    "src/resume_ranker/report/xlsx.py": None,
    "src/resume_ranker/report/html.py": None,
    "src/resume_ranker/report/explain.py": None,
    "src/resume_ranker/report/audit.py": None,
    # C-08
    "src/resume_ranker/structure/__init__.py": None,
    "src/resume_ranker/structure/sections.py": None,
    "src/resume_ranker/structure/dates.py": None,
    "src/resume_ranker/structure/entities.py": None,
    "src/resume_ranker/structure/llm_parse.py": None,
    # C-09
    "src/resume_ranker/jobspec/__init__.py": None,
    "src/resume_ranker/jobspec/compile.py": None,
    "src/resume_ranker/jobspec/schema.py": None,
    "src/resume_ranker/jobspec/review.py": None,
    # C-10
    "src/resume_ranker/scoring/evidence.py": None,
    "src/resume_ranker/scoring/dimensions/s1_required_skills.py": None,
    "src/resume_ranker/scoring/dimensions/s2_preferred_skills.py": None,
    "src/resume_ranker/scoring/dimensions/s8_skill_recency.py": None,
    # C-11
    "src/resume_ranker/embeddings/__init__.py": None,
    "src/resume_ranker/embeddings/client.py": None,
    "src/resume_ranker/scoring/dimensions/s3_semantic.py": None,
    # C-12
    "src/resume_ranker/scoring/dimensions/s4_experience.py": None,
    "src/resume_ranker/scoring/dimensions/s5_title.py": None,
    "src/resume_ranker/scoring/dimensions/s6_domain.py": None,
    "src/resume_ranker/scoring/dimensions/s7_education.py": None,
    "src/resume_ranker/scoring/dimensions/s9_trajectory.py": None,
    "src/resume_ranker/scoring/dimensions/s10_parseability.py": None,
    # C-13
    "src/resume_ranker/scoring/aggregate.py": None,
    "src/resume_ranker/scoring/confidence.py": None,
    "src/resume_ranker/scoring/bands.py": None,
    "src/resume_ranker/scoring/tiebreak.py": None,
    "src/resume_ranker/scoring/filters.py": None,
    # C-14
    "src/resume_ranker/fairness/__init__.py": None,
    "src/resume_ranker/fairness/redaction.py": None,
    "src/resume_ranker/fairness/proxies.py": None,
    "src/resume_ranker/fairness/impact.py": None,
    # C-15
    "src/resume_ranker/config/__init__.py": None,
    "src/resume_ranker/config/root.py": None,
    "src/resume_ranker/cli/__init__.py": None,
    "src/resume_ranker/cli/main.py": None,
    "src/resume_ranker/pipeline.py": None,
}

# Test directories where we want a conftest.py and a stub test module.
UNIT_TEST_DIRS = [
    "tests/unit/ingest",
    "tests/unit/extract_pdf",
    "tests/unit/extract_office",
    "tests/unit/ontology",
    "tests/unit/llm",
    "tests/unit/integrity",
    "tests/unit/report",
    "tests/unit/structure",
    "tests/unit/jobspec",
    "tests/unit/scoring_evidence",
    "tests/unit/scoring_semantic",
    "tests/unit/scoring_profile",
    "tests/unit/scoring_aggregate",
    "tests/property",
    "tests/golden/structure",
    "tests/adversarial",
    "tests/fairness",
    "tests/integration",
    "tests/e2e",
    "tests/benchmark",
    "tests/qa",
]

# Per-component dep-request and changelog files.
COMPONENT_IDS = [
    "C-01", "C-02", "C-03", "C-04", "C-05", "C-06", "C-07",
    "C-08", "C-09", "C-10", "C-11", "C-12", "C-13", "C-14", "C-15", "C-QA",
]


def main() -> None:
    for d in DIRS:
        (ROOT / d).mkdir(parents=True, exist_ok=True)

    for rel in STUB_MODULES:
        path = ROOT / rel
        if not path.exists():
            path.write_text(STUB_BODY, encoding="utf-8")

    for d in UNIT_TEST_DIRS:
        conftest = ROOT / d / "conftest.py"
        if not conftest.exists():
            conftest.write_text(CONFTEXT_STUB_BODY, encoding="utf-8")
        stub = ROOT / d / "test_stub.py"
        if not stub.exists():
            stub.write_text(TEST_STUB_BODY, encoding="utf-8")

    for cid in COMPONENT_IDS:
        depreq = ROOT / f"docs/dep-requests/{cid}.md"
        if not depreq.exists():
            depreq.write_text(f"# Dependency requests for {cid}\n\nNone.\n", encoding="utf-8")
        changelog = ROOT / f"changelog.d/{cid}.feature.md"
        if not changelog.exists():
            changelog.write_text(f"# {cid} feature newsfragment\n\n", encoding="utf-8")

    # Root package init
    (ROOT / "src/resume_ranker/__init__.py").write_text(
        "from __future__ import annotations\n\n__version__ = \"0.1.0\"\n",
        encoding="utf-8",
    )

    # Models package init
    (ROOT / "src/resume_ranker/models/__init__.py").write_text(
        "from __future__ import annotations\n",
        encoding="utf-8",
    )

    # Extract/scoring package inits owned by W0
    (ROOT / "src/resume_ranker/extract/__init__.py").write_text(
        "from __future__ import annotations\n\nfrom resume_ranker.extract.registry import load_extractors\n\n__all__ = [\"load_extractors\"]\n",
        encoding="utf-8",
    )
    (ROOT / "src/resume_ranker/scoring/__init__.py").write_text(
        "from __future__ import annotations\n\nfrom resume_ranker.scoring.registry import load_dimensions\n\n__all__ = [\"load_dimensions\"]\n",
        encoding="utf-8",
    )
    (ROOT / "src/resume_ranker/scoring/dimensions/__init__.py").write_text(
        "from __future__ import annotations\n",
        encoding="utf-8",
    )

    # Data license notices
    (ROOT / "data/ontology/2026.07/LICENSE.esco").write_text(
        "ESCO vocabulary is licensed under CC BY 4.0.\n" "Attribution: European Commission, 2024.\n",
        encoding="utf-8",
    )
    (ROOT / "data/ontology/2026.07/LICENSE.onet").write_text(
        "O*NET data is a US Department of Labor product and is in the public domain in the United States.\n"
        "Users must comply with the O*NET Data Collection Program terms of use.\n",
        encoding="utf-8",
    )

    print("Wave 0 skeleton generated.")


if __name__ == "__main__":
    main()
