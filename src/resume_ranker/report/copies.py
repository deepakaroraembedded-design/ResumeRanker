from __future__ import annotations

from pathlib import Path

from resume_ranker.models.common import Diagnostic, StageResult
from resume_ranker.models.run import RunResult
from resume_ranker.models.scoring import ScoreCard
from resume_ranker.report._helpers import atomic_copy, format_score, safe_filename


def copy_selected_resumes(run: RunResult, out_dir: Path) -> StageResult[tuple[Path, ...]]:
    """Copy source files for selected candidates into ``selected/``.

    TRD §9.1 / FR-905: copies are named ``{rank:03d}_{score}_{candidate_id}_{basename}``;
    originals are left untouched.
    """
    selected_dir = out_dir / "selected"
    selected_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    diagnostics: list[Diagnostic] = []

    for card in run.scorecards:
        if not card.selected:
            continue
        resume = run.resumes.get(card.candidate_id)
        if resume is None or resume.source is None:
            diagnostics.append(
                Diagnostic(
                    stage="S9",
                    code="RPT_WRITE_DIAGNOSTIC",
                    message=f"No source document for selected candidate {card.candidate_id}",
                )
            )
            continue

        source_path = Path(resume.source.path)
        if not source_path.exists():
            diagnostics.append(
                Diagnostic(
                    stage="S9",
                    code="RPT_WRITE_DIAGNOSTIC",
                    message=f"Source file missing for selected candidate {card.candidate_id}: {source_path}",
                )
            )
            continue

        dest = selected_dir / _selected_filename(card, source_path)
        atomic_copy(source_path, dest)
        copied.append(dest)

    return StageResult(value=tuple(copied), diagnostics=tuple(diagnostics))


def _selected_filename(card: ScoreCard, source_path: Path) -> str:
    """Build the destination filename for a selected candidate's source file."""
    rank = card.rank if card.rank is not None else 0
    score = format_score(card.composite)
    basename = safe_filename(source_path.name)
    return f"{rank:03d}_{score}_{card.candidate_id}_{basename}"
