from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from resume_ranker.models.common import StageResult
from resume_ranker.models.run import RunResult
from resume_ranker.protocols import ReportWriter
from resume_ranker.report._helpers import atomic_write_text


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


class RunManifestJsonWriter(ReportWriter):
    """Write the run manifest as ``run_manifest.json``."""

    artefact: ClassVar[str] = "run_manifest.json"

    def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]:
        path = out_dir / self.artefact
        atomic_write_text(path, run.manifest.model_dump_json(indent=2))
        return StageResult(value=path)
