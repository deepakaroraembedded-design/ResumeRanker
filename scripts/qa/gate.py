#!/usr/bin/env python3
"""Run a named QA gate and emit a report."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

REPORTS = Path("docs/qa")


def _run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError as exc:
        return 1, "", str(exc)


def _check(name: str, cmd: list[str], report: list[str]) -> bool:
    code, out, err = _run(cmd)
    ok = code == 0
    status = "PASS" if ok else "FAIL"
    report.append(f"## {name}: {status}\n")
    report.append(f"Command: {' '.join(cmd)}\n")
    if out:
        report.append(f"\n```\n{out}\n```\n")
    if err:
        report.append(f"\n```stderr\n{err}\n```\n")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a QA gate and write a report")
    parser.add_argument("--gate", required=True, choices=("QG0", "QG1", "QG2", "QG3"))
    parser.add_argument("--incremental", action="store_true", help="incremental QG2 run")
    args = parser.parse_args()

    report: list[str] = [f"# QA gate report — {args.gate}\n"]
    if args.incremental:
        report.append("*(incremental run)*\n")

    checks = [
        ("make gate", ["make", "gate"]),
        ("make own", ["make", "own"]),
        ("blind-derivation check", ["python", "scripts/qa/check-blind-derivation.py"]),
        ("traceability audit", ["python", "scripts/qa/trace.py"]),
    ]

    if args.gate in {"QG1", "QG2", "QG3"}:
        checks.append(
            (
                "mutation entry point",
                ["python", "scripts/qa/mutate.py", "--package", "resume_ranker/scoring"],
            )
        )

    all_ok = True
    for name, cmd in checks:
        if not _check(name, cmd, report):
            all_ok = False

    report.append(f"\n## Verdict\n\n{'SIGNED OFF' if all_ok else 'BLOCKED'}\n")

    out_path = REPORTS / f"report-{args.gate}.md"
    out_path.write_text("".join(report), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
