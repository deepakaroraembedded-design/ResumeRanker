from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, ClassVar

from resume_ranker.models.common import StageResult
from resume_ranker.models.jobspec import JobSpec
from resume_ranker.models.run import RunResult
from resume_ranker.models.scoring import ScoreCard
from resume_ranker.protocols import ReportWriter
from resume_ranker.report._helpers import (
    DECISION_SUPPORT_BANNER,
    _serialize_value,
    atomic_write_text,
)


class AuditJsonlWriter(ReportWriter):
    """Write ``audit.jsonl`` with one append-only record per candidate.

    TRD §11.6 / FR-909: sufficient provenance to reconstruct any historical
    decision.
    """

    artefact: ClassVar[str] = "audit.jsonl"

    def write(self, run: RunResult, out_dir: Path) -> StageResult[Path]:
        path = out_dir / self.artefact
        lines: list[str] = []
        for card in run.scorecards:
            record = self._record(card, run)
            lines.append(json.dumps(record, separators=(",", ":"), default=str))

        content = "\n".join(lines)
        if content:
            content += "\n"
        atomic_write_text(path, content)

        return StageResult(value=path)

    def _record(self, card: ScoreCard, run: RunResult) -> dict[str, Any]:
        sub_scores: dict[str, Any] = {}
        for dimension, sub in card.sub_scores.items():
            sub_scores[dimension] = {
                "value": sub.value,
                "evidence": [
                    {
                        "span": ev.span,
                        "quote": ev.quote,
                        "page": ev.page,
                        "source": ev.source,
                    }
                    for ev in sub.evidence
                ],
                "detail": _serialize_value(sub.detail),
                "notes": list(sub.notes),
            }

        return {
            "run_id": run.manifest.run_id,
            "candidate_id": card.candidate_id,
            "config_hash": run.manifest.config_hash,
            "ontology_version": run.manifest.ontology_version,
            "code_version": run.manifest.code_version,
            "model_identifiers": run.manifest.model_identifiers,
            "jobspec_hash": _jobspec_hash(run.jobspec),
            "sub_scores": sub_scores,
            "matched": [_serialize_value(m) for m in card.matched],
            "gaps": [_serialize_value(g) for g in card.gaps],
            "flags": list(card.flags),
            "reason_codes": list(card.reason_codes),
            "selection_verdict": {
                "selected": card.selected,
                "eligible": card.eligible,
                "rank": card.rank,
            },
            "calibration_anchors": run.manifest.calibration_anchors,
            "provenance": _serialize_value(card.provenance),
            "decision_support_banner": DECISION_SUPPORT_BANNER,
        }


def _jobspec_hash(jobspec: JobSpec | None) -> str | None:
    """Return a SHA-256 hash of the resolved JobSpec, or None if absent."""
    if jobspec is None:
        return None
    # model_dump_json does not accept sort_keys; round-trip via json.dumps to get
    # a canonical key order for hashing.
    payload = json.dumps(
        jobspec.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
