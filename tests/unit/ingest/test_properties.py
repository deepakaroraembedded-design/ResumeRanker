from __future__ import annotations

from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ats_scan.ingest.manifest import build_manifest
from ats_scan.models.config import IngestConfig

_PATH_CHARACTERS = "abcdefghijklmnopqrstuvwxyz0123456789_"


@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    files=st.lists(
        st.tuples(
            st.text(_PATH_CHARACTERS, min_size=1, max_size=8).filter(
                lambda s: s not in {"", ".", ".."}
            ),
            st.text(_PATH_CHARACTERS + " \n", min_size=1, max_size=200),
        ),
        min_size=1,
        max_size=10,
        unique_by=lambda x: x[0],
    )
)
def test_manifest_order_is_stable(tmp_path: Path, files: list[tuple[str, str]]) -> None:
    """FR-101: manifest order is sorted by path and independent of filesystem order."""
    for name, content in files:
        path = tmp_path / name
        path.write_text(content)

    result = build_manifest(tmp_path, IngestConfig())
    assert result.ok
    paths = [doc.path for doc in result.value.documents]
    assert paths == sorted(paths)

    # Re-running on the same directory yields the same manifest.
    result2 = build_manifest(tmp_path, IngestConfig())
    assert result2.ok
    assert result.value == result2.value
