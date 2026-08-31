from __future__ import annotations

from enum import StrEnum


class JobSpecCode(StrEnum):
    """Reason codes emitted by the JobSpec compiler stage (TRD §2.5, FR-400)."""

    JD_EMPTY = "JD_EMPTY"
    JD_INVALID_SCHEMA = "JD_INVALID_SCHEMA"
    JD_WRITE_FAILED = "JD_WRITE_FAILED"
    JD_PROXY_KNOCKOUT_UNACKNOWLEDGED = "JD_PROXY_KNOCKOUT_UNACKNOWLEDGED"
