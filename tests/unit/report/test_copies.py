from __future__ import annotations

from pathlib import Path

import pytest

from resume_ranker.models.run import RunResult
from resume_ranker.report.copies import copy_selected_resumes


@pytest.fixture
def source_files(tmp_path: Path, sample_run: RunResult) -> tuple[Path, Path]:
    """Create real source files on disk for the selected-copy tests."""
    pdf_dir = tmp_path / "resumes"
    pdf_dir.mkdir()
    abc = pdf_dir / "abc123.pdf"
    abc.write_text("resume abc", encoding="utf-8")
    def456 = pdf_dir / "def456.pdf"
    def456.write_text("resume def", encoding="utf-8")

    resumes = dict(sample_run.resumes)
    resumes["c_abc123"] = resumes["c_abc123"].model_copy(
        update={"source": resumes["c_abc123"].source.model_copy(update={"path": str(abc)})}
    )
    resumes["c_def456"] = resumes["c_def456"].model_copy(
        update={"source": resumes["c_def456"].source.model_copy(update={"path": str(def456)})}
    )

    run = sample_run.model_copy(update={"resumes": resumes})
    return run, abc, def456


def test_copy_selected_resumes(source_files: tuple[Path, Path, Path], tmp_path: Path) -> None:
    run, abc, _ = source_files
    out_dir = tmp_path / "out"
    result = copy_selected_resumes(run, out_dir)
    assert result.ok
    selected_dir = out_dir / "selected"
    assert selected_dir.exists()

    copied = list(selected_dir.iterdir())
    assert len(copied) == 1
    assert copied[0].name == f"001_87.06_c_abc123_{abc.name}"
    assert copied[0].read_text(encoding="utf-8") == abc.read_text(encoding="utf-8")


def test_copy_selected_resumes_missing_source(tmp_path: Path, sample_run: RunResult) -> None:
    out_dir = tmp_path / "out"
    result = copy_selected_resumes(sample_run, out_dir)
    # The source paths in the fixture are not real files, so copy returns empty
    # tuple and diagnostics without raising.
    assert result.value == ()
    assert any("Source file missing" in d.message for d in result.diagnostics)


def test_copy_selected_resumes_atomic(
    tmp_path: Path, source_files: tuple[Path, Path, Path]
) -> None:
    run, _, _ = source_files
    out_dir = tmp_path / "out"
    copy_selected_resumes(run, out_dir)
    assert not list(out_dir.rglob("*.tmp"))
