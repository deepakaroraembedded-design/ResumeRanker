from __future__ import annotations

import importlib
import pkgutil

import ats_scan
from ats_scan.scoring import registry as scoring_registry


def test_all_ats_scan_modules_importable() -> None:
    """Every module under ats_scan imports without raising at module scope."""
    for _importer, modname, _ispkg in pkgutil.walk_packages(
        ats_scan.__path__, ats_scan.__name__ + "."
    ):
        importlib.import_module(modname)


def test_dimension_registry_contains_all_ids() -> None:
    """The scoring registry contains all ten dimension IDs."""
    registered = scoring_registry.load_dimensions()
    for dim_id in (f"S{i}" for i in range(1, 11)):
        assert dim_id in registered
        assert registered[dim_id].id == dim_id
