from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import ClassVar

from resume_ranker.models.common import StageResult
from resume_ranker.models.run import RunResult
from resume_ranker.protocols import ReportWriter
from resume_ranker.report._helpers import DECISION_SUPPORT_BANNER, atomic_write_text


class DiagnosticsCsvWriter(ReportWriter):
    """Write diagnostic CSV files under ``diagnostics/``.

    TRD §9.1 / FR-910: errors.csv, unmapped_skills.csv and knockout_stats.csv.
    """

    artefact: ClassVar[str] = "diagnostics/*.csv"

    def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]:
        diag_dir = out_dir / "diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)

        self._write_errors_csv(run, diag_dir)
        self._write_knockout_stats_csv(run, diag_dir)
        self._write_unmapped_skills_csv(run, diag_dir)

        return StageResult(value=diag_dir)

    def _write_errors_csv(self, run: RunResult, diag_dir: Path) -> None:
        path = diag_dir / "errors.csv"
        fieldnames = ["stage", "code", "message"]
        output = io.StringIO()
        output.write(f"# {DECISION_SUPPORT_BANNER}\n")
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for diagnostic in run.diagnostics:
            writer.writerow(
                {
                    "stage": diagnostic.stage,
                    "code": diagnostic.code,
                    "message": diagnostic.message,
                }
            )
        atomic_write_text(path, output.getvalue())

    def _write_knockout_stats_csv(self, run: RunResult, diag_dir: Path) -> None:
        path = diag_dir / "knockout_stats.csv"
        fieldnames = ["rule_id", "PASS", "FAIL", "UNVERIFIED", "excluded_share"]
        counts: dict[str, dict[str, int]] = {}
        for card in run.scorecards:
            for ko in card.knockout_results:
                rule_id = ko.id
                verdict = ko.verdict
                bucket = counts.setdefault(rule_id, {"PASS": 0, "FAIL": 0, "UNVERIFIED": 0})
                bucket[verdict] = bucket.get(verdict, 0) + 1

        output = io.StringIO()
        output.write(f"# {DECISION_SUPPORT_BANNER}\n")
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        total = max(len(run.scorecards), 1)
        for rule_id in sorted(counts):
            stats = counts[rule_id]
            writer.writerow(
                {
                    "rule_id": rule_id,
                    "PASS": stats.get("PASS", 0),
                    "FAIL": stats.get("FAIL", 0),
                    "UNVERIFIED": stats.get("UNVERIFIED", 0),
                    "excluded_share": f"{stats.get('FAIL', 0) / total:.2f}",
                }
            )
        atomic_write_text(path, output.getvalue())

    def _write_unmapped_skills_csv(self, run: RunResult, diag_dir: Path) -> None:
        path = diag_dir / "unmapped_skills.csv"
        fieldnames = ["candidate_id", "raw_skill", "sections", "mentions"]
        output = io.StringIO()
        output.write(f"# {DECISION_SUPPORT_BANNER}\n")
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for candidate_id, resume in run.resumes.items():
            for skill in resume.skills:
                if skill.canonical is not None:
                    continue
                writer.writerow(
                    {
                        "candidate_id": candidate_id,
                        "raw_skill": skill.raw,
                        "sections": ";".join(skill.sections),
                        "mentions": skill.mentions,
                    }
                )
        atomic_write_text(path, output.getvalue())
