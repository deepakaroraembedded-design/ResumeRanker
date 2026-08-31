from __future__ import annotations


class AtsScanError(Exception):
    """Base exception for the RESUME-RANKER package."""


class ContractError(AtsScanError):
    """A frozen contract was violated."""


class ConfigurationError(AtsScanError):
    """Configuration is invalid or inconsistent."""
