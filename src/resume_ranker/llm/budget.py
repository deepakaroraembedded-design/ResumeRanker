from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UsageTracker:
    """Accumulates token and cost usage across a run.

    Attributes:
        tokens_in: Total input tokens consumed.
        tokens_out: Total output tokens consumed.
        calls: Number of LLM calls made.
        retries: Number of retry attempts (transport and validation combined).
        cost: Estimated cost in currency units.
    """

    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    retries: int = 0
    cost: float = 0.0

    def add(
        self,
        usage: dict[str, object],
        price_in: float | None = None,
        price_out: float | None = None,
    ) -> None:
        """Record a single call's usage and update cost estimates.

        Args:
            usage: Provider usage dictionary, typically containing
                ``prompt_tokens`` and ``completion_tokens``.
            price_in: Price per million input tokens, or ``None``.
            price_out: Price per million output tokens, or ``None``.
        """
        self.calls += 1
        prompt_tokens = self._as_int(usage.get("prompt_tokens"))
        completion_tokens = self._as_int(usage.get("completion_tokens"))
        if prompt_tokens is not None:
            self.tokens_in += prompt_tokens
            if price_in is not None:
                self.cost += prompt_tokens * price_in / 1_000_000
        if completion_tokens is not None:
            self.tokens_out += completion_tokens
            if price_out is not None:
                self.cost += completion_tokens * price_out / 1_000_000

    @staticmethod
    def _as_int(value: object) -> int | None:
        """Safely convert a usage value to ``int``.

        Args:
            value: A value from a provider usage dictionary.

        Returns:
            The integer value, or ``None`` if it cannot be converted.
        """
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def snapshot(self) -> dict[str, object]:
        """Return a serializable snapshot of the accumulated usage.

        Returns:
            Dictionary with ``tokens_in``, ``tokens_out``, ``calls``,
            ``retries`` and ``cost``.
        """
        return {
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "calls": self.calls,
            "retries": self.retries,
            "cost": round(self.cost, 6),
        }
