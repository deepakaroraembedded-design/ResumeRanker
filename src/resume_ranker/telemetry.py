from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any


class NullTelemetry:
    """No-op telemetry implementation for Wave 0."""

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Generator[None, None, None]:
        """Context manager that records a timing span."""
        yield

    def record(self, name: str, value: Any) -> None:
        """Record a scalar metric."""

    def flush(self) -> None:
        """Flush any buffered telemetry."""


TELEMETRY = NullTelemetry()


@contextmanager
def span(name: str, **attrs: Any) -> Generator[None, None, None]:
    with TELEMETRY.span(name, **attrs):
        yield


def record(name: str, value: Any) -> None:
    TELEMETRY.record(name, value)
