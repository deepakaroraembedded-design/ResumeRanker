from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ats_scan.models.jobspec import JobSpec


def load_jobspec(path: Path) -> JobSpec:
    """Load and validate a hand-authored JobSpec from a YAML or JSON file."""
    text = path.read_text(encoding="utf-8")
    if text.strip().startswith(("{", "[")):
        data: Any = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if data is None:
        raise ValueError(f"empty JobSpec file: {path}")
    return JobSpec.model_validate(data)


def dump_jobspec(spec: JobSpec) -> str:
    """Serialize a JobSpec to a YAML string for review or audit output."""
    return str(yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False))
