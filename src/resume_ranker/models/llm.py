from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMResult[T]:
    """Result of one or more LLM structured calls.

    samples contains the parsed outputs for all independent calls.  If the
    adapter was asked for one sample, samples has length one.
    """

    samples: tuple[T, ...]
    raw: tuple[str, ...] = ()
    usage: dict[str, object] = field(default_factory=dict)
