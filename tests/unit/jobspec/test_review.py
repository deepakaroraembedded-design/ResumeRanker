from __future__ import annotations

from pathlib import Path

import yaml

from resume_ranker.jobspec import is_reviewed, jobspec_path, review_path, write_jobspec
from resume_ranker.models.jobspec import JobSpec


def test_review_paths(output_dir: Path) -> None:
    """Review helpers return deterministic paths inside the output directory."""
    assert jobspec_path(output_dir) == output_dir / "jobspec.yaml"
    assert review_path(output_dir) == output_dir / "jobspec.review.yaml"


def test_is_reviewed_false_when_missing(output_dir: Path) -> None:
    assert is_reviewed(output_dir) is False


def test_is_reviewed_false_when_pending(output_dir: Path) -> None:
    review = output_dir / "jobspec.review.yaml"
    review.write_text(yaml.safe_dump({"state": "pending"}), encoding="utf-8")
    assert is_reviewed(output_dir) is False


def test_is_reviewed_true_when_approved(output_dir: Path) -> None:
    review = output_dir / "jobspec.review.yaml"
    review.write_text(yaml.safe_dump({"state": "approved"}), encoding="utf-8")
    assert is_reviewed(output_dir) is True


def test_write_jobspec_serializes_job_spec(output_dir: Path) -> None:
    spec = JobSpec(job_id="jd_write", title="Write Test")
    path = write_jobspec(spec, output_dir)
    assert path == output_dir / "jobspec.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["job_id"] == "jd_write"
    assert data["title"] == "Write Test"
