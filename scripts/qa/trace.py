#!/usr/bin/env python3
"""Requirement traceability audit scaffold for ATS-Scan.

Parses the TRD for FR/NFR identifiers, collects ``@pytest.mark.covers`` markers
from the test tree, and emits ``docs/qa/traceability.md``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

TRD = Path("docs/TRD.md")
TEST_ROOTS = (Path("tests"),)
OUTPUT = Path("docs/qa/traceability.md")


REQUIREMENT_RE = re.compile(r"^(FR|NFR)-\d+\b")
MOSCOW = frozenset({"M", "S", "C", "W"})
COVERS_RE = re.compile(r"@pytest\.mark\.covers\(([^)]+)\)")


def _parse_requirements() -> dict[str, str]:
    """Extract requirement IDs and their MoSCoW priority from the TRD tables.

    The TRD lists functional requirements in whitespace-aligned tables.  Each
    requirement row begins with an ``FR-xxx`` identifier and ends with the
    single-letter MoSCoW priority in the right-most column.  Group headers such
    as ``FR-700 Scoring`` and appendix cross-references are not requirement rows
    and are ignored because their last token is not a valid priority.
    """
    if not TRD.exists():
        return {}
    requirements: dict[str, str] = {}
    for line in TRD.read_text().splitlines():
        stripped = line.strip()
        match = REQUIREMENT_RE.match(stripped)
        if not match:
            continue
        tokens = stripped.split()
        if not tokens:
            continue
        req_id, priority = tokens[0], tokens[-1]
        if priority in MOSCOW:
            requirements[req_id] = priority
    return requirements


def _collect_covers_markers(root: Path) -> dict[str, list[str]]:
    """Collect requirement IDs covered by each test file."""
    covered: dict[str, list[str]] = {}
    for path in root.rglob("*.py"):
        if not path.is_file() or path.name == "conftest.py":
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for match in COVERS_RE.finditer(text):
            ids = [item.strip().strip("\"'") for item in match.group(1).split(",")]
            for req_id in ids:
                covered.setdefault(req_id, []).append(str(path))
    return covered


def main() -> int:
    parser = argparse.ArgumentParser(description="Requirement traceability audit")
    parser.add_argument("--out", default=str(OUTPUT), help="output markdown file")
    args = parser.parse_args()

    requirements = _parse_requirements()
    covered: dict[str, list[str]] = {}
    for test_root in TEST_ROOTS:
        if test_root.exists():
            covered.update(_collect_covers_markers(test_root))

    out_path = Path(args.out)
    lines = [
        "# Traceability audit\n",
        "| Requirement | Priority | Covered by | Status |\n",
        "|-------------|----------|------------|--------|\n",
    ]
    for req_id in sorted(requirements):
        priority = requirements[req_id]
        files = sorted(set(covered.get(req_id, [])))
        status = "covered" if files else "uncovered"
        files_str = "; ".join(files) if files else "—"
        lines.append(f"| {req_id} | {priority} | {files_str} | {status} |\n")

    uncovered_must = [r for r, p in requirements.items() if p == "M" and r not in covered]
    if uncovered_must:
        lines.append("\n## Uncovered Must-have requirements\n")
        for req_id in uncovered_must:
            lines.append(f"- {req_id}\n")

    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
