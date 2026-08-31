from __future__ import annotations

from pathlib import Path
from typing import Any

from resume_ranker.models.common import Diagnostic, StageResult
from resume_ranker.models.run import RunResult
from resume_ranker.report.audit import AuditJsonlWriter
from resume_ranker.report.copies import copy_selected_resumes
from resume_ranker.report.csv import CsvWriter
from resume_ranker.report.diagnostics import DiagnosticsCsvWriter
from resume_ranker.report.explain import format_explanation_text, format_score_derivation
from resume_ranker.report.html import HtmlReportWriter
from resume_ranker.report.json import RunManifestJsonWriter, ScorecardJsonWriter
from resume_ranker.report.xlsx import XlsxWriter

__all__ = [
    "AuditJsonlWriter",
    "CsvWriter",
    "DiagnosticsCsvWriter",
    "HtmlReportWriter",
    "RunManifestJsonWriter",
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
