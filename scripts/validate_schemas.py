#!/usr/bin/env python3
"""Generate JSON schemas from the frozen Pydantic models."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ats_scan.models import (
    CanonicalResume,
    ExtractedText,
    JobSpec,
    RunManifest,
    RunResult,
    ScoreCard,
    SourceDocument,
)

MODELS = {
    "source_document": SourceDocument,
    "extracted_text": ExtractedText,
    "canonical_resume": CanonicalResume,
    "jobspec": JobSpec,
    "scorecard": ScoreCard,
    "run_manifest": RunManifest,
    "run_result": RunResult,
}


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: validate_schemas.py <output_dir> <src_dir>", file=sys.stderr)
        return 2

    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, model in MODELS.items():
        if hasattr(model, "model_rebuild"):
            model.model_rebuild()
        schema = model.model_json_schema()
        path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
