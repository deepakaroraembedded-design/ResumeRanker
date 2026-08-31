from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from resume_ranker.protocols import TextExtractor

_REGISTRY: dict[str, TextExtractor] = {}


def extractor(cls: type[TextExtractor]) -> type[TextExtractor]:
    """Class decorator that registers a TextExtractor implementation."""
    inst = cls()
    key = cls.__name__
    if key in _REGISTRY:
        raise RuntimeError(f"duplicate extractor registration: {key}")
    _REGISTRY[key] = inst
    return cls


def load_extractors() -> Mapping[str, TextExtractor]:
    """Import all extractor sub-packages and return the registered instances."""
    import resume_ranker.extract as extract_pkg

    for _importer, modname, ispkg in pkgutil.iter_modules(extract_pkg.__path__):
        if ispkg:
            importlib.import_module(f"{extract_pkg.__name__}.{modname}")
    return MappingProxyType(_REGISTRY)
