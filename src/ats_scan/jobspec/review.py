from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from ats_scan.jobspec.schema import dump_jobspec
from ats_scan.models.jobspec import JobSpec

REVIEW_FILENAME = "jobspec.review.yaml"
JOBSPEC_FILENAME = "jobspec.yaml"


def review_path(output_dir: Path) -> Path:
    """Return the path to the review-state sidecar file."""
    return output_dir / REVIEW_FILENAME


def jobspec_path(output_dir: Path) -> Path:
    """Return the path to the emitted JobSpec review file."""
    return output_dir / JOBSPEC_FILENAME


def write_jobspec(spec: JobSpec, output_dir: Path, review_mode: bool = False) -> Path:
    """Write the compiled JobSpec to disk and optionally a pending review sidecar."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = jobspec_path(output_dir)
    path.write_text(dump_jobspec(spec), encoding="utf-8")
    if review_mode:
        review = review_path(output_dir)
        review.write_text(
            yaml.safe_dump({"state": "pending", "jobspec": path.name}, sort_keys=False),
            encoding="utf-8",
        )
    return path


def is_reviewed(output_dir: Path) -> bool:
    """Return True iff the review sidecar exists and is marked approved."""
    path = review_path(output_dir)
    if not path.exists():
        return False
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return isinstance(data, dict) and data.get("state") == "approved"
