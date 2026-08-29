#!/usr/bin/env python3
"""Mutation testing entry point.

The QA plan specifies ``mutmut`` or ``cosmic-ray``.  Neither is pinned in the
Wave-0 lockfile, so this script first checks for a usable tool, records a
dependency request if one is missing, and otherwise delegates to the tool.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEP_REQUEST = Path("docs/dep-requests/C-QA.md")
REPORT = Path("docs/qa/mutants-QG1.md")


def _record_missing_tool(tool: str) -> None:
    DEP_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    text = f"# C-QA dependency request\n\nRequested: {tool}\nReason: mutation testing per QA_PLAN §4.\n"
    DEP_REQUEST.write_text(text, encoding="utf-8")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = f"# Mutation testing triage — QG1\n\nTool `{tool}` is not installed.\n\n"
    report += "A dependency request has been recorded in " + str(DEP_REQUEST) + ".\n"
    REPORT.write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run mutation testing for a package")
    parser.add_argument("--package", default="ats_scan/scoring", help="package path")
    args = parser.parse_args()

    tool = shutil.which("mutmut") or shutil.which("cosmic-ray")
    if tool is None:
        # mutmut is the preferred tool in the QA plan.
        _record_missing_tool("mutmut")
        print("mutmut is not available; dependency request recorded in docs/dep-requests/C-QA.md")
        return 0

    try:
        subprocess.run([tool, "run", "--paths-to-mutate", args.package], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Mutation run failed: {exc}", file=sys.stderr)
        return exc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
