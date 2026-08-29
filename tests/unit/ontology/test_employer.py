from __future__ import annotations

import pytest

from ats_scan.ontology import EmployerNormalizer


@pytest.fixture
def normalizer() -> EmployerNormalizer:
    return EmployerNormalizer()


class TestEmployerNormalise:
    def test_strips_legal_suffixes(self, normalizer: EmployerNormalizer) -> None:
        assert normalizer.normalise("Northwind Logistics, Inc.") == "northwind logistics"

    def test_resolves_aliases(self, normalizer: EmployerNormalizer) -> None:
        assert normalizer.normalise("IBM Corporation") == "international business machines"
        assert normalizer.normalise("AWS") == "amazon web services"
        assert normalizer.normalise("Google") == "alphabet"

    def test_returns_none_for_empty_input(self, normalizer: EmployerNormalizer) -> None:
        assert normalizer.normalise("") is None
        assert normalizer.normalise("   ") is None
