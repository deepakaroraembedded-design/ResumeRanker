from __future__ import annotations

from resume_ranker.fairness.impact import (
    AdverseImpactReport,
    GroupImpact,
    compute_adverse_impact_report,
)
from resume_ranker.fairness.proxies import (
    FairnessConfigError,
    forbidden_knockout_attributes,
    validate_knockout_rule,
)
from resume_ranker.fairness.redaction import (
    BlindRedactor,
    redact_text,
    write_reidentification_sidecar,
)

__all__ = [
    "AdverseImpactReport",
    "BlindRedactor",
    "FairnessConfigError",
    "GroupImpact",
    "compute_adverse_impact_report",
    "forbidden_knockout_attributes",
    "redact_text",
    "validate_knockout_rule",
    "write_reidentification_sidecar",
]
