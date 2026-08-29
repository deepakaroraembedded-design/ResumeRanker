from __future__ import annotations


class AtsScanError(Exception):
    """Base exception for the ATS-Scan package."""


class ContractError(AtsScanError):
    """A frozen contract was violated."""


class ConfigurationError(AtsScanError):
    """Configuration is invalid or inconsistent."""
