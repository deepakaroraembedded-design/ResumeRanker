#!/usr/bin/env python3
"""Verify that the oracle was derived before reading any implementation."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ORACLE_DIR = Path("tests/qa/oracle")
READ_LOG = Path("docs/qa/read-log.md")

# Map oracle module -> the implementation files the QA agent must not read first.
IMPLEMENTATION_FILES: dict[str, list[str]] = {
    "s1.py": ["src/ats_scan/scoring/dimensions/s1_required_skills.py"],
    "s2.py": ["src/ats_scan/scoring/dimensions/s2_preferred_skills.py"],
    "s3.py": ["src/ats_scan/scoring/dimensions/s3_semantic.py"],
    "s4.py": ["src/ats_scan/scoring/dimensions/s4_experience.py"],
    "s5.py": ["src/ats_scan/scoring/dimensions/s5_title.py"],
    "s6.py": ["src/ats_scan/scoring/dimensions/s6_domain.py"],
    "s7.py": ["src/ats_scan/scoring/dimensions/s7_education.py"],
    "s8.py": ["src/ats_scan/scoring/dimensions/s8_skill_recency.py"],
    "s9.py": ["src/ats_scan/scoring/dimensions/s9_trajectory.py"],
    "s10.py": ["src/ats_scan/scoring/dimensions/s10_parseability.py"],
    "aggregate.py": ["src/ats_scan/scoring/aggregate.py"],
    "confidence.py": ["src/ats_scan/scoring/confidence.py"],
    "bands.py": ["src/ats_scan/scoring/bands.py"],
    "tiebreak.py": ["src/ats_scan/scoring/tiebreak.py"],
}


def _git_first_commit_time(path: str) -> datetime | None:
    """Return the timestamp of the first commit touching ``path``."""
    try:
        result = subprocess.run(
            ["git", "log", "--follow", "--format=%cI", "--", path],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    lines = [line for line in result.stdout.splitlines() if line]
    if not lines:
        return None
    earliest = min(lines)
    return datetime.fromisoformat(earliest).astimezone(UTC)


def _parse_read_log() -> dict[str, datetime | None]:
    """Parse the read-log table for recorded implementation-read dates."""
    if not READ_LOG.exists():
        return {}
    rows: dict[str, datetime | None] = {}
    for line in READ_LOG.read_text().splitlines():
        if line.startswith("|") and "First commit" not in line:
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p]
            if len(parts) < 3:
                continue
            module, _, read_raw = parts[0], parts[1], parts[2]
            if read_raw.lower() in {"not yet read", "tbd", ""}:
                rows[module] = None
            else:
                try:
                    rows[module] = datetime.fromisoformat(read_raw).astimezone(UTC)
                except ValueError:
                    rows[module] = None
    return rows


def _check_oracle_imports(module: Path) -> list[str]:
    """Return violations if the oracle imports anything outside ats_scan.models."""
    tree = ast.parse(module.read_text(), filename=str(module))
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("ats_scan") and alias.name != "ats_scan.models":
                    violations.append(f"{module.name}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name.startswith("ats_scan") and module_name != "ats_scan.models":
                violations.append(f"{module.name}: from {module_name}")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify oracle blind derivation")
    parser.add_argument(
        "--strict", action="store_true", help="fail if a module is missing from the log"
    )
    args = parser.parse_args()

    read_log = _parse_read_log()
    failures = []

    for module, _impl_files in IMPLEMENTATION_FILES.items():
        module_path = ORACLE_DIR / module
        if not module_path.exists():
            failures.append(f"missing oracle module: {module}")
            continue

        violations = _check_oracle_imports(module_path)
        if violations:
            failures.extend(violations)

        first_commit = _git_first_commit_time(str(module_path))
        if first_commit is None:
            failures.append(f"{module}: no git history found")
            continue

        read_time = read_log.get(module)
        if read_time is None:
            if args.strict:
                failures.append(f"{module}: not recorded in read log")
            continue

        if read_time < first_commit:
            failures.append(
                f"{module}: implementation read at {read_time.isoformat()} "
                f"predates oracle first commit at {first_commit.isoformat()}"
            )

    if failures:
        print("Blind-derivation check FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print("OK: oracle modules were committed before any recorded implementation read.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
