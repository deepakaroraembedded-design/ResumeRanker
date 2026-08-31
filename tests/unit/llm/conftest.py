from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from resume_ranker.llm.adapter import LLMAdapter
from resume_ranker.llm.budget import UsageTracker
from resume_ranker.llm.cache import Cache
from resume_ranker.llm.transport import RecordedTransport
from resume_ranker.models.config import LLMConfig
from resume_ranker.models.run import RunContext


class SampleModel(BaseModel):
    """A tiny schema used in adapter tests."""

    name: str
    score: int | None = None


class SpanModel(BaseModel):
    """A schema with evidence-span fields for span verification tests."""

    claim: str
    span: tuple[int, int] | None = None
    quote: str | None = None


class RequiredSpanModel(BaseModel):
    """A schema where the span is required, forcing a retry if invalid."""

    claim: str
    span: tuple[int, int]
    quote: str | None = None


class SampleWithSpans(BaseModel):
    """A schema containing a list of span dicts."""

    claims: list[dict[str, object]] = []


@pytest.fixture
def llm_config() -> LLMConfig:
    """Default test configuration with short timeouts and minimal retries."""
    return LLMConfig(
        mode="hybrid",
        provider="openai",
        model="gpt-4o-mini",
        concurrency=2,
        timeout_s=5.0,
        max_retries=1,
        price_per_mtok_in=0.5,
        price_per_mtok_out=1.5,
    )


@pytest.fixture
def run_context(tmp_path: Path) -> RunContext:
    """A run context that points the cache into a temporary directory."""
    return RunContext(run_id="run_test_001", cache_dir=tmp_path / "cache")


@pytest.fixture
def cache(run_context: RunContext) -> Cache:
    """A fresh cache for each test."""
    return Cache(run_context.cache_dir / "llm.db")


@pytest.fixture
def budget() -> UsageTracker:
    """A fresh usage tracker for each test."""
    return UsageTracker()


@pytest.fixture
def transport() -> RecordedTransport:
    """An empty recorded transport; tests populate it per case."""
    return RecordedTransport(recordings={})


@pytest.fixture
def adapter(
    llm_config: LLMConfig,
    cache: Cache,
    budget: UsageTracker,
    transport: RecordedTransport,
) -> LLMAdapter:
    """A fully wired LLM adapter using a fixed nonce for deterministic tests."""
    return LLMAdapter(
        config=llm_config,
        cache=cache,
        budget=budget,
        transport=transport,
        nonce="testnonce",
    )
