from __future__ import annotations

from pathlib import Path
from typing import Any

from ats_scan.models.common import Diagnostic, StageResult
from ats_scan.models.run import RunResult
from ats_scan.report.audit import AuditJsonlWriter
from ats_scan.report.copies import copy_selected_resumes
from ats_scan.report.csv import CsvWriter
from ats_scan.report.diagnostics import DiagnosticsCsvWriter
from ats_scan.report.explain import format_explanation_text, format_score_derivation
from ats_scan.report.html import HtmlReportWriter
from ats_scan.report.json import ScorecardJsonWriter
from ats_scan.report.xlsx import XlsxWriter

__all__ = [
    "AuditJsonlWriter",
    "CsvWriter",
    "DiagnosticsCsvWriter",
    "HtmlReportWriter",
    "ScorecardJsonWriter",
    "XlsxWriter",
    "copy_selected_resumes",
    "format_explanation_text",
    "format_score_derivation",
    "write_all_reports",
]


def write_all_reports(run: RunResult, out_dir: Path) -> dict[str, StageResult[Any]]:
    """Write every report artefact to *out_dir*.

    A failure in one writer is captured as a diagnostic and does not prevent the
    remaining artefacts from being written (TRD §10.3).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    writers = [
        CsvWriter(),
        XlsxWriter(),
        ScorecardJsonWriter(),
        HtmlReportWriter(),
        AuditJsonlWriter(),
        DiagnosticsCsvWriter(),
    ]
    results: dict[str, StageResult[Any]] = {}
    for writer in writers:
        try:
            results[writer.artefact] = writer.write(run, out_dir)
        except Exception as exc:
            results[writer.artefact] = StageResult(
                value=None,
                diagnostics=(
                    Diagnostic(
                        stage="S9",
                        code="RPT_WRITE_DIAGNOSTIC",
                        message=f"{writer.artefact} writer failed: {exc}",
                    ),
                ),
            )
    results["selected"] = copy_selected_resumes(run, out_dir)
    return results
