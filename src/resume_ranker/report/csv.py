from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import ClassVar

from resume_ranker.models.common import StageResult
from resume_ranker.models.run import RunResult
from resume_ranker.models.scoring import ScoreCard
from resume_ranker.protocols import ReportWriter
from resume_ranker.report._helpers import (
    DECISION_SUPPORT_BANNER,
    _candidate_file,
    _candidate_name,
    atomic_write_text,
    format_score,
    matched_required,
    missing_required,
    relevant_years,
    semicolon_join,
    sub_score_value,
)


class CsvWriter(ReportWriter):
    """Write the ranked ``scores.csv`` artefact.

    Columns and order are exactly those defined in TRD §9.2.
    """

    artefact: ClassVar[str] = "scores.csv"

    _FIELDNAMES: ClassVar[tuple[str, ...]] = (
        "rank",
        "candidate_id",
        "file",
        "name",
        "composite",
        "band",
        "selected",
        "eligible",
        "confidence",
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
        "S7",
        "S8",
        "S9",
        "S10",
        "matched_required",
        "missing_required",
        "relevant_years",
        "flags",
        "reason_codes",
        "explanation",
    )

    def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]:
        path = out_dir / self.artefact
        output = io.StringIO()
        output.write(f"# {DECISION_SUPPORT_BANNER}\n")
        writer = csv.DictWriter(output, fieldnames=list(self._FIELDNAMES))
        writer.writeheader()

        for card in run.scorecards:
            row = self._row(card, run)
            writer.writerow(row)

        atomic_write_text(path, output.getvalue())
        return StageResult(value=path)

    def _row(self, card: ScoreCard, run: RunResult) -> dict[str, str]:
        scorecard = card
        return {
            "rank": str(scorecard.rank) if scorecard.rank is not None else "",
            "candidate_id": scorecard.candidate_id,
            "file": _candidate_file(scorecard, run),
            "name": _candidate_name(scorecard, run),
            "composite": format_score(scorecard.composite),
            "band": scorecard.band.value if scorecard.band else "",
            "selected": "true" if scorecard.selected else "false",
            "eligible": "true" if scorecard.eligible else "false",
            "confidence": format_score(scorecard.confidence),
            **{f"S{i}": format_score(sub_score_value(scorecard, f"S{i}")) for i in range(1, 11)},
            "matched_required": matched_required(scorecard),
            "missing_required": missing_required(scorecard),
            "relevant_years": relevant_years(scorecard),
            "flags": semicolon_join(scorecard.flags),
            "reason_codes": semicolon_join(scorecard.reason_codes),
            "explanation": scorecard.explanation,
        }
