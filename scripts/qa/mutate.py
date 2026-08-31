#!/usr/bin/env python3
"""Mutation testing entry point.

The QA plan specifies ``mutmut`` or ``cosmic-ray``. This script now expects
``mutmut`` to be pinned in the dev dependency group (W0-002 / W0-003). It runs
mutmut, exports the CI/CD stats, and writes a triage report to
``docs/qa/mutants-QG2.md``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DEP_REQUEST = Path("docs/dep-requests/C-QA.md")
REPORT = Path("docs/qa/mutants-QG2.md")

# QA_PLAN §4.2 thresholds.
THRESHOLDS: dict[str, float] = {
    "resume_ranker.scoring": 0.90,
}
DEFAULT_THRESHOLD = 0.60


def _record_missing_tool(tool: str) -> None:
    """Record that the mutation tool is missing and write a stub report."""
    DEP_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    text = f"# C-QA dependency request\n\nRequested: {tool}\nReason: mutation testing per QA_PLAN §4.\n"
    DEP_REQUEST.write_text(text, encoding="utf-8")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = f"# Mutation testing triage — QG2\n\nTool `{tool}` is not installed.\n\n"
    report += "A dependency request has been recorded in " + str(DEP_REQUEST) + ".\n"
    REPORT.write_text(report, encoding="utf-8")


def _module_prefix(package: str) -> str:
    """Convert a filesystem package path to a Python module prefix."""
    return package.replace("/", ".").rstrip(".")


def _threshold_for(prefix: str) -> float:
    """Return the mutation-score threshold for the requested package."""
    for package, threshold in sorted(THRESHOLDS.items(), key=lambda kv: -len(kv[0])):
        if prefix.startswith(package.replace("/", ".")):
            return threshold
    return DEFAULT_THRESHOLD


def _run_mutmut() -> dict[str, int]:
    """Run mutmut and export the CI/CD stats.

    Captures stdout and prints only the final progress line so the QA gate
    report is not flooded with mutmut's animation frames.
    """
    run_result = subprocess.run(["mutmut", "run"], capture_output=True, text=True, check=True)
    for line in reversed(run_result.stdout.splitlines()):
        stripped = line.strip()
        if stripped and "1788/1788" in stripped:
            print(stripped)
            break
    subprocess.run(["mutmut", "export-cicd-stats"], check=True)
    stats_path = Path("mutants/mutmut-cicd-stats.json")
    return json.loads(stats_path.read_text(encoding="utf-8"))


def _results_for_prefix(prefix: str) -> list[str]:
    """Return mutmut results lines that belong to the requested package."""
    result = subprocess.run(
        ["mutmut", "results"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines()]
    return [line for line in lines if line.startswith(prefix + ".") and "__mutmut_" in line]


def _classify(line: str) -> str:
    """Return the status word at the end of a mutmut results line."""
    return line.rsplit(":", 1)[-1].strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run mutation testing for a package")
    parser.add_argument("--package", default="resume_ranker/scoring", help="package path")
    args = parser.parse_args()

    tool = shutil.which("mutmut")
    if tool is None:
        _record_missing_tool("mutmut")
        print("mutmut is not available; dependency request recorded in docs/dep-requests/C-QA.md")
        return 0

    try:
        stats = _run_mutmut()
    except subprocess.CalledProcessError as exc:
        print(f"Mutation run failed: {exc}", file=sys.stderr)
        return exc.returncode

    total = int(stats.get("total", 0))
    killed = int(stats.get("killed", 0))
    survived = int(stats.get("survived", 0))
    no_tests = int(stats.get("no_tests", 0))
    score = killed / total if total else 0.0

    prefix = _module_prefix(args.package)
    threshold = _threshold_for(prefix)
    ok = score >= threshold

    package_lines = _results_for_prefix(prefix)
    package_survivors = [line for line in package_lines if _classify(line) == "survived"]
    package_no_tests = [line for line in package_lines if _classify(line) == "no_tests"]

    report_lines = [
        "# Mutation testing triage — QG2\n\n",
        f"Package: `{args.package}`\n",
        f"Module prefix: `{prefix}`\n\n",
        "## Global mutmut run\n\n",
        f"- Total mutants: {total}\n",
        f"- Killed: {killed}\n",
        f"- Survived: {survived}\n",
        f"- No tests: {no_tests}\n",
        f"- Mutation score: {score:.1%}\n",
        f"- Threshold: {threshold:.0%}\n",
        f"- Verdict: {'PASS' if ok else 'FAIL'}\n\n",
        f"## Package survivors in `{prefix}` ({len(package_survivors)})\n\n",
    ]

    if package_survivors:
        for line in package_survivors:
            report_lines.append(f"- `{line}`\n")
    else:
        report_lines.append("No surviving mutants in the requested package.\n")

    if package_no_tests:
        report_lines.append(f"\n## Package mutants with no tests in `{prefix}` ({len(package_no_tests)})\n\n")
        for line in package_no_tests:
            report_lines.append(f"- `{line}`\n")

    report_lines.append(
        "\n## Triage guidance\n\n"
        "Every surviving mutant must be classified per QA_PLAN §4.4:\n\n"
        "| Class | Action |\n"
        "|---|---|\n"
        "| Genuine gap | Add a killing test or file an S3 defect against the owner |\n"
        "| Equivalent | Record justification; suppress by mutant ID |\n"
        "| Unreachable | File an S3 defect — dead code in a scoring engine is a specification question |\n"
        "| Intolerable | Engineering-lead sign-off required |\n"
    )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("".join(report_lines), encoding="utf-8")

    print(f"Mutation score: {score:.1%} (killed {killed}, survived {survived}, no_tests {no_tests}, total {total})")
    print(f"Wrote {REPORT}")

    if not ok:
        print(
            f"FAIL: mutation score {score:.1%} is below the {threshold:.0%} threshold for {args.package}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
