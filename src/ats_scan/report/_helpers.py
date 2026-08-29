from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from ats_scan.models.run import RunResult
from ats_scan.models.scoring import ScoreCard

DECISION_SUPPORT_BANNER: str = (
    "This output is decision support only. A human reviewer must confirm every "
    "advance or reject decision before any candidate is contacted or excluded."
)


def safe_filename(name: str) -> str:
    """Return a filesystem-safe filename by replacing unsafe characters.

    TRD §9.1: output naming derives from a sanitised basename plus the
    candidate id.
    """
    return re.sub(r"[^\w.\-]", "_", name)


def format_score(value: float | None) -> str:
    """Return a two-decimal string, or an empty string if *value* is None."""
    if value is None:
        return ""
    return f"{value:.2f}"


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically write *content* to *path* using a temp file and rename.

    TRD §10.3: output artefacts are written to temporary files and atomically
    renamed, so a partially written file never appears.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically write *data* to *path* using a temp file and rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def atomic_copy(src: Path, dst: Path) -> None:
    """Atomically copy *src* to *dst* using a temp file and rename."""
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def sub_score_value(card: ScoreCard, dimension: str) -> float | None:
    """Return the value of dimension *dimension* from *card*, or None."""
    sub = card.sub_scores.get(dimension)
    if sub is None:
        return None
    return sub.value


def matched_required(card: ScoreCard) -> str:
    """Return a semicolon-separated list of matched required criteria.

    TRD §9.2: ``matched_required`` lists canonical skills matched, with match
    values.
    """
    parts: list[str] = []
    for match in card.matched:
        parts.append(f"{match.criterion}={match.match:.2f}")
    return ";".join(parts)


def missing_required(card: ScoreCard) -> str:
    """Return a semicolon-separated list of unmet required criteria.

    TRD §9.2: ``missing_required`` lists unmet criteria with weights.
    """
    parts: list[str] = []
    for gap in card.gaps:
        parts.append(f"{gap.criterion}(w={gap.weight})")
    return ";".join(parts)


def relevant_years(card: ScoreCard) -> str:
    """Return relevant years from S4 detail if available, else empty string."""
    s4 = card.sub_scores.get("S4")
    if s4 is None:
        return ""
    val = s4.detail.get("relevant_years")
    if isinstance(val, (int, float)):
        return f"{val:.2f}"
    return ""


def semicolon_join(items: tuple[str, ...]) -> str:
    """Join strings with semicolons, returning an empty string when empty."""
    return ";".join(items)


def _candidate_name(card: ScoreCard, run: RunResult) -> str:
    """Return the candidate name, or empty string when blind mode is active."""
    resume = run.resumes.get(card.candidate_id)
    if resume is None or resume.identity is None:
        return ""
    return resume.identity.full_name or ""


def _candidate_file(card: ScoreCard, run: RunResult) -> str:
    """Return the source file path for a candidate, or empty string."""
    resume = run.resumes.get(card.candidate_id)
    if resume is None or resume.source is None:
        return ""
    return resume.source.path


def _serialize_value(obj: Any) -> Any:
    """Recursively convert Pydantic models and dataclasses to plain dicts."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _serialize_value(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [_serialize_value(v) for v in obj]
    return obj
