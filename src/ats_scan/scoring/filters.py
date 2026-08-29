from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from ats_scan.errors import ConfigurationError
from ats_scan.models.config import FairnessConfig
from ats_scan.models.jobspec import JobSpec, KnockoutRule
from ats_scan.models.resume import CanonicalResume
from ats_scan.models.scoring import KnockoutResult


class KnockoutEvaluator(Protocol):
    """Protocol for a single knockout rule evaluator."""

    def __call__(
        self, rule: KnockoutRule, resume: CanonicalResume, spec: JobSpec
    ) -> KnockoutResult: ...


def _rule_references_forbidden(rule: KnockoutRule, forbidden: tuple[str, ...]) -> bool:
    """Return True if *rule.rule* references a forbidden attribute."""
    text = rule.rule.lower()
    return any(attr.lower() in text for attr in forbidden)


def evaluate_knockouts(
    resume: CanonicalResume,
    spec: JobSpec,
    cfg: FairnessConfig,
    *,
    evaluators: Mapping[str, KnockoutEvaluator] | None = None,
) -> tuple[bool, tuple[KnockoutResult, ...]]:
    """Evaluate knockout rules with three-valued logic per TRD §5.2.

    A rule can only exclude on an explicit ``FAIL``. ``UNVERIFIED`` keeps the
    candidate eligible but produces a ``KO_UNVERIFIED`` flag for the caller to
    record. Rules that reference a fairness-forbidden attribute raise
    ``ConfigurationError`` per FR-605 / FR-1105.

    Returns:
        ``(eligible, results)`` where ``eligible`` is False if any rule failed.
    """
    evaluators = evaluators or {}
    forbidden = cfg.forbid_knockouts_on

    results: list[KnockoutResult] = []
    eligible = True

    for rule in spec.knockouts:
        if _rule_references_forbidden(rule, forbidden):
            raise ConfigurationError(f"Knockout rule {rule.id!r} references a forbidden attribute")
        evaluator = evaluators.get(rule.id)
        if evaluator is None:
            result = KnockoutResult(id=rule.id, verdict="UNVERIFIED")
        else:
            result = evaluator(rule, resume, spec)
        results.append(result)
        if result.verdict == "FAIL":
            eligible = False

    return eligible, tuple(results)
