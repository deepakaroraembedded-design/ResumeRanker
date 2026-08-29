#!/usr/bin/env python3
"""Generate Wave 0 repository skeleton and stubs for ATS-Scan."""
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
    "src/ats_scan",
    "src/ats_scan/models",
    "src/ats_scan/extract",
    "src/ats_scan/extract/pdf",
    "src/ats_scan/extract/ocr",
    "src/ats_scan/extract/office",
    "src/ats_scan/extract/plain",
    "src/ats_scan/ingest",
    "src/ats_scan/ontology",
    "src/ats_scan/llm",
    "src/ats_scan/llm/prompts",
    "src/ats_scan/llm/schemas",
    "src/ats_scan/integrity",
    "src/ats_scan/report",
    "src/ats_scan/structure",
    "src/ats_scan/jobspec",
    "src/ats_scan/embeddings",
    "src/ats_scan/scoring",
    "src/ats_scan/scoring/dimensions",
    "src/ats_scan/fairness",
    "src/ats_scan/config",
    "src/ats_scan/cli",

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
    "src/ats_scan/ingest/__init__.py": None,
    "src/ats_scan/ingest/manifest.py": None,
    # C-02
    "src/ats_scan/extract/pdf/__init__.py": None,
    "src/ats_scan/extract/pdf/extractor.py": None,
    "src/ats_scan/extract/ocr/__init__.py": None,
    "src/ats_scan/extract/ocr/extractor.py": None,
    # C-03
    "src/ats_scan/extract/office/__init__.py": None,
    "src/ats_scan/extract/office/extractor.py": None,
    "src/ats_scan/extract/plain/__init__.py": None,
    "src/ats_scan/extract/plain/extractor.py": None,
    # C-04
    "src/ats_scan/ontology/__init__.py": None,
    "src/ats_scan/ontology/loader.py": None,
    "src/ats_scan/ontology/match.py": None,
    "src/ats_scan/ontology/titles.py": None,
    # C-05
    "src/ats_scan/llm/__init__.py": None,
    "src/ats_scan/llm/adapter.py": None,
    "src/ats_scan/llm/cache.py": None,
    "src/ats_scan/llm/budget.py": None,
    # C-06
    "src/ats_scan/integrity/__init__.py": None,
    "src/ats_scan/integrity/hidden_text.py": None,
    "src/ats_scan/integrity/stuffing.py": None,
    "src/ats_scan/integrity/injection.py": None,
    # C-07
    "src/ats_scan/report/__init__.py": None,
    "src/ats_scan/report/csv.py": None,
    "src/ats_scan/report/xlsx.py": None,
    "src/ats_scan/report/html.py": None,
    "src/ats_scan/report/explain.py": None,
    "src/ats_scan/report/audit.py": None,
    # C-08
    "src/ats_scan/structure/__init__.py": None,
    "src/ats_scan/structure/sections.py": None,
    "src/ats_scan/structure/dates.py": None,
    "src/ats_scan/structure/entities.py": None,
    "src/ats_scan/structure/llm_parse.py": None,
    # C-09
    "src/ats_scan/jobspec/__init__.py": None,
    "src/ats_scan/jobspec/compile.py": None,
    "src/ats_scan/jobspec/schema.py": None,
    "src/ats_scan/jobspec/review.py": None,
    # C-10
    "src/ats_scan/scoring/evidence.py": None,
    "src/ats_scan/scoring/dimensions/s1_required_skills.py": None,
    "src/ats_scan/scoring/dimensions/s2_preferred_skills.py": None,
    "src/ats_scan/scoring/dimensions/s8_skill_recency.py": None,
    # C-11
    "src/ats_scan/embeddings/__init__.py": None,
    "src/ats_scan/embeddings/client.py": None,
    "src/ats_scan/scoring/dimensions/s3_semantic.py": None,
    # C-12
    "src/ats_scan/scoring/dimensions/s4_experience.py": None,
    "src/ats_scan/scoring/dimensions/s5_title.py": None,
    "src/ats_scan/scoring/dimensions/s6_domain.py": None,
    "src/ats_scan/scoring/dimensions/s7_education.py": None,
    "src/ats_scan/scoring/dimensions/s9_trajectory.py": None,
    "src/ats_scan/scoring/dimensions/s10_parseability.py": None,
    # C-13
    "src/ats_scan/scoring/aggregate.py": None,
    "src/ats_scan/scoring/confidence.py": None,
    "src/ats_scan/scoring/bands.py": None,
    "src/ats_scan/scoring/tiebreak.py": None,
    "src/ats_scan/scoring/filters.py": None,
    # C-14
    "src/ats_scan/fairness/__init__.py": None,
    "src/ats_scan/fairness/redaction.py": None,
    "src/ats_scan/fairness/proxies.py": None,
    "src/ats_scan/fairness/impact.py": None,
    # C-15
    "src/ats_scan/config/__init__.py": None,
    "src/ats_scan/config/root.py": None,
    "src/ats_scan/cli/__init__.py": None,
    "src/ats_scan/cli/main.py": None,
    "src/ats_scan/pipeline.py": None,
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
    (ROOT / "src/ats_scan/__init__.py").write_text(
        "from __future__ import annotations\n\n__version__ = \"0.1.0\"\n",
        encoding="utf-8",
    )

    # Models package init
    (ROOT / "src/ats_scan/models/__init__.py").write_text(
        "from __future__ import annotations\n",
        encoding="utf-8",
    )

    # Extract/scoring package inits owned by W0
    (ROOT / "src/ats_scan/extract/__init__.py").write_text(
        "from __future__ import annotations\n\nfrom ats_scan.extract.registry import load_extractors\n\n__all__ = [\"load_extractors\"]\n",
        encoding="utf-8",
    )
    (ROOT / "src/ats_scan/scoring/__init__.py").write_text(
        "from __future__ import annotations\n\nfrom ats_scan.scoring.registry import load_dimensions\n\n__all__ = [\"load_dimensions\"]\n",
        encoding="utf-8",
    )
    (ROOT / "src/ats_scan/scoring/dimensions/__init__.py").write_text(
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
