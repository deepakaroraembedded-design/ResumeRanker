#!/usr/bin/env python3
"""Verify that a branch only touches files owned by the calling component."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


OWNERSHIP: dict[str, tuple[str, ...]] = {
    "W0": (
        "src/resume_ranker/models/",
        "src/resume_ranker/protocols.py",
        "src/resume_ranker/errors.py",
        "src/resume_ranker/codes.py",
        "src/resume_ranker/cache.py",
        "src/resume_ranker/telemetry.py",
        "src/resume_ranker/extract/__init__.py",
        "src/resume_ranker/extract/registry.py",
        "src/resume_ranker/scoring/__init__.py",
        "src/resume_ranker/scoring/registry.py",
        "src/resume_ranker/scoring/dimensions/__init__.py",
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/fakes/",
        "tests/corpus/",
        "tests/test_fakes_",
        "tests/test_import_all_modules.py",
        "pyproject.toml",
        "uv.lock",
        "Makefile",
        ".importlinter",
        ".github/",
        "AGENTS.md",
        "opencode.json",
        ".opencode/",
        "scripts/",
        "docs/IMPLEMENTATION_PLAN.md",
        "docs/QA_PLAN.md",
        "docs/TRD.md",
        "docs/contracts/",
        "docs/contract-change/",
        "README.md",
        "Dockerfile",
    ),
    "C-QA": (
        "tests/qa/",
        "docs/qa/",
        "scripts/qa/",
        "changelog.d/C-QA.",
        "docs/dep-requests/C-QA.md",
        "docs/contract-change/C-QA-",
    ),
    "C-01": ("src/resume_ranker/ingest/", "tests/unit/ingest/", "changelog.d/C-01.", "docs/dep-requests/C-01.md", "docs/contract-change/C-01-"),
    "C-02": ("src/resume_ranker/extract/pdf/", "src/resume_ranker/extract/ocr/", "tests/unit/extract_pdf/", "tests/adversarial/test_pdf_", "changelog.d/C-02.", "docs/dep-requests/C-02.md", "docs/contract-change/C-02-"),
    "C-03": ("src/resume_ranker/extract/office/", "src/resume_ranker/extract/plain/", "tests/unit/extract_office/", "changelog.d/C-03.", "docs/dep-requests/C-03.md", "docs/contract-change/C-03-"),
    "C-04": ("src/resume_ranker/ontology/", "data/ontology/", "data/titles/", "tests/unit/ontology/", "tests/property/test_ontology_", "changelog.d/C-04.", "docs/dep-requests/C-04.md", "docs/contract-change/C-04-"),
    "C-05": ("src/resume_ranker/llm/", "tests/unit/llm/", "changelog.d/C-05.", "docs/dep-requests/C-05.md", "docs/contract-change/C-05-"),
    "C-06": ("src/resume_ranker/integrity/", "tests/unit/integrity/", "tests/adversarial/test_integrity_", "changelog.d/C-06.", "docs/dep-requests/C-06.md", "docs/contract-change/C-06-"),
    "C-07": ("src/resume_ranker/report/", "tests/unit/report/", "changelog.d/C-07.", "docs/dep-requests/C-07.md", "docs/contract-change/C-07-"),
    "C-08": ("src/resume_ranker/structure/", "tests/unit/structure/", "tests/golden/structure/", "changelog.d/C-08.", "docs/dep-requests/C-08.md", "docs/contract-change/C-08-"),
    "C-09": ("src/resume_ranker/jobspec/", "tests/unit/jobspec/", "changelog.d/C-09.", "docs/dep-requests/C-09.md", "docs/contract-change/C-09-"),
    "C-10": ("src/resume_ranker/scoring/evidence.py", "src/resume_ranker/scoring/dimensions/s1_required_skills.py", "src/resume_ranker/scoring/dimensions/s2_preferred_skills.py", "src/resume_ranker/scoring/dimensions/s8_skill_recency.py", "tests/unit/scoring_evidence/", "changelog.d/C-10.", "docs/dep-requests/C-10.md", "docs/contract-change/C-10-"),
    # The shared Wave-0 xfail test file spans all three scoring components; each
    # component removes the marker for the dimensions it owns.
    "C-11": ("src/resume_ranker/embeddings/", "src/resume_ranker/scoring/dimensions/s3_semantic.py", "tests/unit/scoring_semantic/", "tests/unit/scoring_evidence/test_dimension_xfail.py", "changelog.d/C-11.", "docs/dep-requests/C-11.md", "docs/contract-change/C-11-"),
    "C-12": ("src/resume_ranker/scoring/dimensions/s4_experience.py", "src/resume_ranker/scoring/dimensions/s5_title.py", "src/resume_ranker/scoring/dimensions/s6_domain.py", "src/resume_ranker/scoring/dimensions/s7_education.py", "src/resume_ranker/scoring/dimensions/s9_trajectory.py", "src/resume_ranker/scoring/dimensions/s10_parseability.py", "tests/unit/scoring_profile/", "tests/unit/scoring_evidence/test_dimension_xfail.py", "changelog.d/C-12.", "docs/dep-requests/C-12.md", "docs/contract-change/C-12-"),
    "C-13": ("src/resume_ranker/scoring/aggregate.py", "src/resume_ranker/scoring/confidence.py", "src/resume_ranker/scoring/bands.py", "src/resume_ranker/scoring/tiebreak.py", "src/resume_ranker/scoring/filters.py", "tests/unit/scoring_aggregate/", "tests/property/test_aggregate_", "changelog.d/C-13.", "docs/dep-requests/C-13.md", "docs/contract-change/C-13-"),
    "C-14": ("src/resume_ranker/fairness/", "tests/fairness/", "changelog.d/C-14.", "docs/dep-requests/C-14.md", "docs/contract-change/C-14-"),
    "C-15": ("src/resume_ranker/cli/", "src/resume_ranker/config/", "src/resume_ranker/pipeline.py", "tests/integration/", "tests/e2e/", "tests/benchmark/", "changelog.d/C-15.", "docs/dep-requests/C-15.md", "docs/contract-change/C-15-"),
}


EXCLUDED_PATHS = {
    ".gitignore",
    ".python-version",
    ".coverage",
    "uv.lock",
    "README.md",
}


def current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def infer_component(branch: str) -> str | None:
    if branch == "main" or branch == "master":
        return "W0"
    if branch.startswith("feat/"):
        prefix = branch.split("/")[1]
        if prefix.startswith("C-"):
            parts = prefix.split("-")
            if parts[1] == "QA":
                return "C-QA"
            if parts[1].isdigit():
                return f"C-{parts[1]:0>2}"
    return None


def changed_files(base: str | None) -> list[str]:
    if base is None:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = []
        for line in result.stdout.splitlines():
            if not line:
                continue
            path = line[3:].strip()
            # git status can list directories with a trailing slash when the
            # directory contains only untracked files; expand them.
            if path.endswith("/"):
                files.extend(_expand_dir(path.rstrip("/")))
            else:
                files.append(path)
        return files
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _expand_dir(path: str) -> list[str]:
    root = Path(path)
    if not root.exists():
        return []
    return [str(p.relative_to(Path.cwd())) for p in root.rglob("*") if p.is_file()]


def matches(path: str, prefixes: tuple[str, ...]) -> bool:
    for prefix in prefixes:
        if prefix.endswith("/") and (path == prefix.rstrip("/") or path.startswith(prefix)):
            return True
        if path.startswith(prefix):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that a branch only touches owned paths")
    parser.add_argument("--base", default=None, help="git base ref to diff against")
    parser.add_argument("--component", default=None, help="component ID (e.g., C-01)")
    args = parser.parse_args()

    component = args.component or infer_component(current_branch())
    if component is None:
        print("Could not infer component from branch; pass --component", file=sys.stderr)
        return 1

    if component not in OWNERSHIP:
        print(f"Unknown component: {component}", file=sys.stderr)
        return 1

    allowed = OWNERSHIP[component]
    # C-QA is allowed to read scripts/ but only write scripts/qa/; W0 owns the rest.
    if component == "W0":
        allowed = tuple(p for p in allowed if p != "scripts/qa/")

    violations = []
    for path in changed_files(args.base):
        if path in EXCLUDED_PATHS:
            continue
        if not matches(path, allowed):
            violations.append(path)

    if violations:
        print(f"Ownership violations for {component}:")
        for v in violations:
            print(f"  {v}")
        return 1

    print(f"OK: all changes in {component} owned paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
