from __future__ import annotations

import importlib
import pkgutil

import resume_ranker
from resume_ranker.scoring import registry as scoring_registry


def test_all_resume_ranker_modules_importable() -> None:
    """Every module under resume_ranker imports without raising at module scope."""
    for _importer, modname, _ispkg in pkgutil.walk_packages(
        resume_ranker.__path__, resume_ranker.__name__ + "."
    ):
        importlib.import_module(modname)


def test_dimension_registry_contains_all_ids() -> None:
    """The scoring registry contains all ten dimension IDs."""
    registered = scoring_registry.load_dimensions()
    for dim_id in (f"S{i}" for i in range(1, 11)):
        assert dim_id in registered
        assert registered[dim_id].id == dim_id
