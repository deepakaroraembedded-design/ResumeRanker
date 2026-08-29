from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ats_scan.protocols import Dimension

_REGISTRY: dict[str, Dimension] = {}


def dimension(cls: type[Dimension]) -> type[Dimension]:
    """Class decorator that registers a Dimension implementation."""
    inst = cls()
    dim_id = cls.id
    if dim_id in _REGISTRY:
        raise RuntimeError(f"duplicate dimension id: {dim_id}")
    _REGISTRY[dim_id] = inst
    return cls


def load_dimensions() -> Mapping[str, Dimension]:
    """Import all dimension modules and return the registered instances."""
    import ats_scan.scoring.dimensions as dims_pkg

    for _importer, modname, ispkg in pkgutil.iter_modules(dims_pkg.__path__):
        if not ispkg:
            importlib.import_module(f"{dims_pkg.__name__}.{modname}")
    return MappingProxyType(_REGISTRY)
