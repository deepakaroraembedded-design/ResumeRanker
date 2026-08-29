from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ats_scan.jobspec import JobSpecCompiler
from ats_scan.models.run import RunContext


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def run_context(output_dir: Path) -> RunContext:
    return RunContext(run_id="run_test", output_dir=output_dir)


@pytest.fixture
def compiler() -> JobSpecCompiler:
    return JobSpecCompiler()


@pytest.fixture
def read_corpus_jd() -> Iterator:
    def _read(name: str) -> str:
        path = Path("tests/corpus/jobspecs") / name
        return path.read_text(encoding="utf-8")

    return _read
