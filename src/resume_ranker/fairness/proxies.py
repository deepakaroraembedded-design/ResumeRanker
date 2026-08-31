from __future__ import annotations

import re
from collections.abc import Iterable

from resume_ranker.models.config import FairnessConfig


class FairnessConfigError(ValueError):
    """A fairness configuration value is invalid."""


def forbidden_knockout_attributes(cfg: FairnessConfig) -> frozenset[str]:
    """Return the set of attributes that knockout rules may not reference.

    The list is loaded from :attr:`FairnessConfig.forbid_knockouts_on` and is
    handed to the aggregation/filter stage (C-13) for enforcement per FR-605.
    """
    return frozenset(cfg.forbid_knockouts_on)


def validate_knockout_rule(rule: str, forbidden: Iterable[str]) -> None:
    """Raise :class:`FairnessConfigError` if *rule* references a forbidden attribute.

    The check is case-insensitive and uses word boundaries to avoid matching
    forbidden attributes as substrings of unrelated words (e.g. 'gender' inside
    'transgender').

    Implements the knockout proxy guard from TRD §11.2 and FR-605.
    """
    lowered = rule.lower()
    for attr in forbidden:
        pattern = re.compile(r"\b" + re.escape(attr.lower()) + r"\b")
        if pattern.search(lowered):
            raise FairnessConfigError(
                f"Knockout rule references forbidden attribute '{attr}': {rule}"
            )
