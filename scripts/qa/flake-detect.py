#!/usr/bin/env python3
"""Detect flaky tests by running the suite multiple times and comparing outcomes."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _run(test_path: str, run_id: int) -> tuple[int, str]:
    cmd = ["python", "-m", "pytest", test_path, "-q", "--tb=short"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect flaky tests")
    parser.add_argument("--path", default="tests", help="test path to run")
    parser.add_argument("--runs", type=int, default=3, help="number of runs")
    parser.add_argument("--report", default="docs/qa/flakes.md", help="report file")
    args = parser.parse_args()

    outcomes: list[tuple[int, str]] = []
    for i in range(args.runs):
        code, output = _run(args.path, i)
        outcomes.append((code, output))
        print(f"Run {i + 1}: exit {code}")

    codes = [code for code, _ in outcomes]
    uniform = all(c == codes[0] for c in codes)

    report_lines = ["# Flake detection report\n"]
    for i, (code, output) in enumerate(outcomes, 1):
        report_lines.append(f"## Run {i} (exit {code})\n")
        report_lines.append(f"\n```\n{output}\n```\n")
    report_lines.append(f"\n## Uniform outcome: {uniform}\n")

    Path(args.report).write_text("".join(report_lines), encoding="utf-8")
    print(f"Wrote {args.report}")
    return 0 if uniform else 1


if __name__ == "__main__":
    raise SystemExit(main())
