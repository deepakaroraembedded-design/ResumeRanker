from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from ats_scan.models.common import StageResult
from ats_scan.models.run import RunResult
from ats_scan.protocols import ReportWriter
from ats_scan.report._helpers import atomic_write_text


class ScorecardJsonWriter(ReportWriter):
    """Write one JSON ScoreCard file per candidate under ``candidates/``."""

    artefact: ClassVar[str] = "candidates/*.scorecard.json"

    def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]:
        candidates_dir = out_dir / "candidates"
        candidates_dir.mkdir(parents=True, exist_ok=True)

        for card in run.scorecards:
            path = candidates_dir / f"{card.candidate_id}.scorecard.json"
            atomic_write_text(path, card.model_dump_json(indent=2))

        return StageResult(value=candidates_dir)
