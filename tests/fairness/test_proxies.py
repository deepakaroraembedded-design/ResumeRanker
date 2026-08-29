from __future__ import annotations

import pytest

from ats_scan.fairness.proxies import (
    FairnessConfigError,
    forbidden_knockout_attributes,
    validate_knockout_rule,
)
from ats_scan.models.config import FairnessConfig

DEFAULT_FORBIDDEN = frozenset(
    ["age", "gender", "nationality", "marital_status", "employment_gaps", "graduation_year"]
)


def test_forbidden_knockout_attributes_from_config() -> None:
    """The forbidden list is read from FairnessConfig.forbid_knockouts_on."""
    cfg = FairnessConfig()
    attrs = forbidden_knockout_attributes(cfg)
    assert attrs == DEFAULT_FORBIDDEN

    cfg_custom = FairnessConfig(forbid_knockouts_on=("age", "gender"))
    assert forbidden_knockout_attributes(cfg_custom) == frozenset(["age", "gender"])


def test_validate_knockout_rule_rejects_forbidden() -> None:
    """Rules that reference a forbidden attribute raise FairnessConfigError."""
    with pytest.raises(FairnessConfigError, match="age"):
        validate_knockout_rule("candidate age must be under 40", DEFAULT_FORBIDDEN)

    with pytest.raises(FairnessConfigError, match="gender"):
        validate_knockout_rule("gender is female", DEFAULT_FORBIDDEN)

    with pytest.raises(FairnessConfigError, match="employment_gaps"):
        validate_knockout_rule("No employment_gaps", DEFAULT_FORBIDDEN)


def test_validate_knockout_rule_case_insensitive() -> None:
    """The forbidden-attribute check is case-insensitive."""
    with pytest.raises(FairnessConfigError, match="graduation_year"):
        validate_knockout_rule("Must list GRADUATION_YEAR", DEFAULT_FORBIDDEN)


def test_validate_knockout_rule_allows_unrelated_substrings() -> None:
    """Forbidden attributes must appear as whole words, not substrings."""
    # "gender" inside "transgender" does not have a word boundary and is ignored.
    validate_knockout_rule("transgender-inclusive policy", frozenset(["gender"]))
    # "age" inside "wage" is preceded by a word character and is ignored.
    validate_knockout_rule("minimum wage rule", frozenset(["age"]))
    # "nationality" inside "nationalities" is a substring and is ignored.
    validate_knockout_rule("dual nationalities", frozenset(["nationality"]))


def test_validate_knockout_rule_allows_clean_rules() -> None:
    """Rules that do not reference forbidden attributes pass validation."""
    validate_knockout_rule("Has Python and AWS experience", DEFAULT_FORBIDDEN)
    validate_knockout_rule("Willing to relocate to London", DEFAULT_FORBIDDEN)
