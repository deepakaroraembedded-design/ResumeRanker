from __future__ import annotations

import pytest

# Component-specific fixtures live here.


def pytest_configure(config: pytest.Config) -> None:
    """Register the C-QA requirement-coverage marker."""
    config.addinivalue_line("markers", "covers(id): marks a test as covering a TRD requirement")
