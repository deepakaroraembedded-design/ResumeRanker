from __future__ import annotations

import asyncio
import hashlib
import json
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypeVar

import pydantic
from pydantic import BaseModel, ValidationError

from resume_ranker.codes import ReasonCode
from resume_ranker.errors import ConfigurationError
from resume_ranker.llm.budget import UsageTracker
from resume_ranker.llm.cache import Cache
from resume_ranker.llm.prompts import PromptTemplate, load_template, render
from resume_ranker.llm.transport import (
    LLMTransportError,
    OpenAIHTTPTransport,
    RecordedTransport,
    RetryableError,
    Transport,
)
from resume_ranker.models.common import Diagnostic, StageResult
from resume_ranker.models.config import LLMConfig
from resume_ranker.models.llm import LLMResult
from resume_ranker.models.run import RunContext

T = TypeVar("T")


# Mapping from trace prefix to the pipeline stage that should appear in any
# diagnostic produced for that call.  The trace convention is owned by the LLM
# adapter: callers are expected to use a prefix matching the stage where the LLM
# is invoked.
_TRACE_STAGE: dict[str, str] = {
    "parse": "S3",
    "compile": "S5",
    "semantic": "S7",
    "transferable": "S7",
    "explain": "S9",
}


async def _backoff(attempt: int) -> None:
    """Sleep for an exponentially increasing duration with jitter.

    TRD §6.3 requires exponential backoff with jitter on 429/5xx responses.
    The backoff is applied by the adapter around the transport call.

    Args:
        attempt: Zero-based retry attempt number.
    """
    base = 2.0**attempt
    jitter = random.uniform(0, base)
    await asyncio.sleep(base + jitter)


def _stage_from_trace(trace: str) -> str:
    """Return the pipeline stage for a trace identifier.

    Args:
        trace: Trace string, conventionally ``prefix:detail``.

    Returns:
        The pipeline stage, defaulting to ``"S7"`` for unknown prefixes.
    """
    prefix = trace.split(":", 1)[0]
    return _TRACE_STAGE.get(prefix, "S7")


def _schema_for[T](schema_type: type[T]) -> dict[str, object]:
    """Generate a JSON schema object for *schema_type*.

    Supports Pydantic ``BaseModel`` classes and dataclasses via Pydantic's
    ``TypeAdapter``.

    Args:
        schema_type: The schema class to describe.

    Returns:
        A JSON-serializable schema dictionary.

    Raises:
        ConfigurationError: if a schema cannot be generated for the type.
    """
    try:
        if issubclass(schema_type, BaseModel):
            return schema_type.model_json_schema()
        return pydantic.TypeAdapter(schema_type).json_schema()
    except Exception as exc:
        msg = f"Cannot generate JSON schema for {schema_type}: {exc}"
        raise ConfigurationError(msg) from exc


def _extract_quarantined_spans(
    variables: Mapping[str, object],
) -> Sequence[tuple[int, int]]:
    """Return quarantined spans from *variables*, if provided.

    Callers may pass the key ``quarantined_spans`` to flag injection-detector
    spans that should be removed from the source text before the prompt is sent.

    Args:
        variables: Adapter variables.

    Returns:
        A sequence of half-open span tuples.
    """
    raw = variables.get("quarantined_spans")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return ()
    spans: list[tuple[int, int]] = []
    for item in raw:
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes)) and len(item) == 2:
            try:
                spans.append((int(item[0]), int(item[1])))
            except (TypeError, ValueError):
                continue
    return spans


def _is_span(value: object) -> bool:
    """Return ``True`` if *value* looks like a ``[start, end]`` span."""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return len(value) == 2 and all(isinstance(x, int) for x in value)
    return False


def _span_bounds(value: object) -> tuple[int, int] | None:
    """Return ``(start, end)`` for a span-like value, or ``None``."""
    if _is_span(value):
        return (int(value[0]), int(value[1]))  # type: ignore[index]
    return None


def _verify_spans(data: dict[str, object], text: str) -> dict[str, object]:
    """Recursively validate and drop invalid evidence spans.

    Any returned span is checked against the source text and the field is dropped
    if it does not match.  Spans that are out of bounds are considered invalid.
    If the span object includes a ``quote`` field, the quote must equal the slice
    of *text* at the span.

    This implements FR-306 as required by the adapter contract.

    Args:
        data: Parsed JSON response as a dictionary.
        text: Source text that spans index into.

    Returns:
        A copy of *data* with invalid spans removed.
    """

    def _valid(span: tuple[int, int], quote: str | None) -> bool:
        start, end = span
        if start < 0 or end > len(text) or start > end:
            return False
        return quote is None or text[start:end] == quote

    def visit(obj: object) -> tuple[object, bool]:
        if isinstance(obj, dict):
            result: dict[str, object] = {}
            changed = False
            for key, value in obj.items():
                # Drop a span field (dict or list) that carries an invalid span.
                if isinstance(value, dict):
                    span = _span_bounds(value.get("span"))
                    if span is not None:
                        quote = value.get("quote")
                        if isinstance(quote, str) and not _valid(span, quote):
                            changed = True
                            continue
                        if not _valid(span, None):
                            changed = True
                            continue
                elif _is_span(value) and key in {"span", "evidence_span", "cited_span"}:
                    # If the parent dict also has a sibling "quote" field, use it
                    # to verify the span text (FR-306).
                    sibling_quote = obj.get("quote") if isinstance(obj, dict) else None
                    q = sibling_quote if isinstance(sibling_quote, str) else None
                    bounds = _span_bounds(value)
                    if bounds is not None and not _valid(bounds, q):
                        changed = True
                        continue
                elif isinstance(value, list):
                    # A list of spans may be a top-level cited_spans list.
                    new_list: list[object] = []
                    list_changed = False
                    for item in value:
                        if isinstance(item, dict):
                            span = _span_bounds(item.get("span"))
                            if span is not None:
                                quote = item.get("quote")
                                q = quote if isinstance(quote, str) else None
                                if not _valid(span, q):
                                    list_changed = True
                                    continue
                        elif _is_span(item):
                            bounds = _span_bounds(item)
                            if bounds is not None and not _valid(bounds, None):
                                list_changed = True
                                continue
                        new_list.append(item)
                    if list_changed:
                        value = new_list
                        changed = True
                new_value, child_changed = visit(value)
                result[key] = new_value
                changed = changed or child_changed
            return result, changed
        if isinstance(obj, list):
            result_list: list[object] = []
            changed = False
            for item in obj:
                if isinstance(item, dict):
                    span = _span_bounds(item.get("span"))
                    if span is not None:
                        quote = item.get("quote")
                        q = quote if isinstance(quote, str) else None
                        if not _valid(span, q):
                            changed = True
                            continue
                elif _is_span(item):
                    bounds = _span_bounds(item)
                    if bounds is not None and not _valid(bounds, None):
                        changed = True
                        continue
                new_item, child_changed = visit(item)
                result_list.append(new_item)
                changed = changed or child_changed
            return result_list, changed
        return obj, False

    result, _ = visit(data)
    return result  # type: ignore[return-value]


def _strip_json_fences(raw: str) -> str:
    """Remove markdown JSON fences from a raw response, if present.

    Args:
        raw: Raw response text from a model.

    Returns:
        The text with leading and trailing fences removed.
    """
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


class LLMAdapter:
    """Provider-agnostic LLM adapter implementing the ``LLMClient`` protocol.

    The adapter is responsible for prompt rendering, injection hardening,
    caching, schema validation, evidence-span verification, retries, token/cost
    accounting and graceful degradation.  It delegates the actual network call
    to a pluggable :class:`Transport`.
    """

    def __init__(
        self,
        *,
        config: LLMConfig,
        cache: Cache,
        budget: UsageTracker,
        transport: Transport,
        semaphore: asyncio.Semaphore | None = None,
        nonce: str | None = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            config: LLM configuration.
            cache: SQLite-backed response cache.
            budget: Token and cost accumulator.
            transport: Transport implementation (recorded, HTTP, etc.).
            semaphore: Optional concurrency semaphore; defaults to *config.concurrency*.
            nonce: Optional per-run nonce; a random one is generated if omitted.
        """
        self._config = config
        self._cache = cache
        self._budget = budget
        self._transport = transport
        self._semaphore = semaphore or asyncio.Semaphore(config.concurrency)
        self._nonce = nonce or _random_nonce()

    async def structured(
        self,
        *,
        template: str,
        variables: Mapping[str, object],
        schema: type[T],
        samples: int = 1,
        trace: str,
    ) -> StageResult[LLMResult[T]]:
        """Execute a schema-constrained LLM call.

        Implements the :class:`LLMClient` protocol.  On persistent failure the
        stage degrades to ``StageResult(value=None, LLM_DEGRADED)`` rather than
        raising, as required by TRD §6.2 and the ``degrade rather than fail``
        principle (TRD §2.5).

        Args:
            template: Name of the prompt template to use.
            variables: Values to substitute into the template.
            schema: Pydantic model or dataclass describing the expected response.
            samples: Number of independent samples to request.
            trace: Logical trace identifier for the call.

        Returns:
            A :class:`StageResult` containing an :class:`LLMResult` or a
            degradation diagnostic.
        """
        if self._config.mode == "offline":
            diag = Diagnostic(
                stage=_stage_from_trace(trace),
                code=str(ReasonCode.DETERMINISTIC_MODE),
                message="LLM call skipped because the run is in offline mode.",
            )
            return StageResult(value=None, diagnostics=(diag,))

        if not self._config.provider:
            diag = Diagnostic(
                stage=_stage_from_trace(trace),
                code=str(ReasonCode.LLM_DEGRADED),
                message="No LLM provider is configured.",
            )
            return StageResult(value=None, diagnostics=(diag,))

        template_obj = load_template(template)
        json_schema = _schema_for(schema)
        schema_json = json.dumps(json_schema)
        quarantined_spans = _extract_quarantined_spans(variables)

        rendered, source_text = render(
            template_obj,
            variables,
            nonce=self._nonce,
            quarantined_spans=quarantined_spans,
            max_content_length=200_000,
            schema_json=schema_json,
        )

        samples_out: list[T] = []
        raw_outputs: list[str] = []
        usages: list[dict[str, object]] = []
        failed = False

        for sample_index in range(samples):
            value, raw, usage = await self._execute_sample(
                template=template_obj,
                rendered=rendered,
                schema=schema,
                source_text=source_text,
                trace=trace,
                sample_index=sample_index,
            )
            if value is None:
                failed = True
                continue
            samples_out.append(value)
            raw_outputs.append(raw)
            usages.append(usage)
            self._budget.add(usage, self._config.price_per_mtok_in, self._config.price_per_mtok_out)

        if failed or not samples_out:
            diag = Diagnostic(
                stage=_stage_from_trace(trace),
                code=str(ReasonCode.LLM_DEGRADED),
                message=f"LLM call failed for {trace}; all validation retries exhausted.",
            )
            return StageResult(value=None, diagnostics=(diag,))

        def _as_int(value: object) -> int:
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            return 0

        total_usage: dict[str, object] = {
            "prompt_tokens": sum(_as_int(u.get("prompt_tokens", 0)) for u in usages),
            "completion_tokens": sum(_as_int(u.get("completion_tokens", 0)) for u in usages),
            "total_tokens": sum(_as_int(u.get("total_tokens", 0)) for u in usages),
        }
        result = LLMResult(
            samples=tuple(samples_out),
            raw=tuple(raw_outputs),
            usage=total_usage,
        )
        return StageResult(value=result)

    async def _execute_sample(
        self,
        *,
        template: PromptTemplate,
        rendered: str,
        schema: type[T],
        source_text: str | None,
        trace: str,
        sample_index: int,
    ) -> tuple[T | None, str, dict[str, object]]:
        """Produce one validated sample, using the cache and retries.

        The method attempts the call up to three times: the original prompt, a
        repair prompt with the validation error, and a reduced-scope prompt that
        asks the model to omit uncertain fields.  If all attempts fail, the
        sample is degraded.

        Args:
            template: The loaded prompt template.
            rendered: The fully rendered prompt.
            schema: Expected response schema.
            source_text: Source text for span verification, or ``None``.
            trace: Logical trace identifier.
            sample_index: Zero-based sample index (included in the cache key).

        Returns:
            Tuple of ``(parsed_value, raw_response, usage_dict)``.  *parsed_value*
            is ``None`` if the sample could not be validated.
        """
        model_id = self._config.model or self._config.provider or "unknown"
        canonical_prompt = rendered.replace(self._nonce, "{{NONCE}}")
        cache_key = self._cache.key(
            model_id=model_id,
            template_version=f"{template.name}-v{template.version}",
            prompt=canonical_prompt,
            sample_index=sample_index,
        )

        cached = await self._cache.get(cache_key)
        if cached is not None:
            raw = cached.decode("utf-8")
            value, error = self._parse_validate(raw, schema, source_text)
            if error is None:
                return value, raw, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        attempts = [
            ("initial", rendered),
            (
                "repair",
                rendered
                + "\n\nThe previous response failed validation. Please correct the JSON and return a valid response matching the schema.",
            ),
            (
                "reduced",
                rendered
                + "\n\nReturn only the fields you are certain about. Omit uncertain fields and ensure the response is valid JSON that matches the schema.",
            ),
        ]

        last_raw = ""
        last_usage: dict[str, object] = {}
        for _name, attempt_prompt in attempts:
            try:
                raw, usage = await self._call_with_retry(attempt_prompt, trace)
            except LLMTransportError as exc:
                self._budget.retries += 1
                last_raw = str(exc)
                last_usage = {}
                continue
            last_raw = raw
            last_usage = usage
            value, error = self._parse_validate(raw, schema, source_text)
            if error is None:
                await self._cache.put(cache_key, raw.encode("utf-8"))
                return value, raw, usage
            self._budget.retries += 1

        return None, last_raw, last_usage

    async def _call_with_retry(
        self,
        prompt: str,
        trace: str,
    ) -> tuple[str, dict[str, object]]:
        """Issue a transport call with bounded retries and per-call timeout.

        TRD §6.3 requires exponential backoff with jitter on 429/5xx responses
        and a per-call timeout.  The semaphore limits concurrency to
        *config.concurrency*.

        Args:
            prompt: Rendered prompt to send.
            trace: Logical trace identifier.

        Returns:
            Raw response text and usage dictionary.

        Raises:
            LLMTransportError: if all retries are exhausted.
        """
        last_exc: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                async with self._semaphore:
                    return await asyncio.wait_for(
                        self._transport.call(
                            prompt=prompt,
                            temperature=0.0,
                            timeout=self._config.timeout_s,
                            trace=trace,
                        ),
                        timeout=self._config.timeout_s + 5.0,
                    )
            except RetryableError as exc:
                last_exc = exc
                self._budget.retries += 1
                if attempt < self._config.max_retries:
                    await _backoff(attempt)
            except TimeoutError as exc:
                last_exc = exc
                self._budget.retries += 1
                if attempt < self._config.max_retries:
                    await _backoff(attempt)

        msg = f"LLM transport failed after {self._config.max_retries + 1} attempts: {last_exc}"
        raise LLMTransportError(msg) from last_exc

    def _parse_validate(
        self,
        raw: str,
        schema: type[T],
        source_text: str | None,
    ) -> tuple[T | None, str | None]:
        """Parse *raw*, verify evidence spans, and validate against *schema*.

        Args:
            raw: Raw response text.
            schema: Expected schema.
            source_text: Source text for span verification, or ``None``.

        Returns:
            Tuple of ``(parsed_value, error_message)``.  *parsed_value* is
            ``None`` if parsing or validation fails.
        """
        text = _strip_json_fences(raw)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON: {exc}"

        if not isinstance(data, dict):
            return None, "Response must be a JSON object"

        if source_text is not None:
            data = _verify_spans(data, source_text)

        try:
            if issubclass(schema, BaseModel):
                parsed: T = schema.model_validate(data)
            else:
                parsed = pydantic.TypeAdapter(schema).validate_python(data)
            return parsed, None
        except ValidationError as exc:
            return None, f"Schema validation failed: {exc}"
        except Exception as exc:
            return None, f"Validation error: {exc}"


def _random_nonce() -> str:
    """Return a random 16-character hex nonce."""
    import secrets

    return secrets.token_hex(8)


def create_llm_adapter(
    run_ctx: RunContext,
    llm_config: LLMConfig,
    transport: Transport | None = None,
) -> LLMAdapter:
    """Create a production-ready LLM adapter for a run.

    The cache is placed under ``run_ctx.cache_dir``.  The nonce is derived from
    the run id so that it is stable across restarts of the same run while still
    appearing random to an attacker.  If no transport is supplied, one is built
    from *llm_config.provider*.

    Args:
        run_ctx: Run context with ``cache_dir`` and ``run_id``.
        llm_config: LLM configuration.
        transport: Optional transport override, mainly for tests.

    Returns:
        An initialized :class:`LLMAdapter`.

    Raises:
        ConfigurationError: if the provider is unsupported.
    """
    cache_dir = run_ctx.cache_dir or Path(".ats-cache")
    cache = Cache(cache_dir / "llm_cache.db")
    budget = UsageTracker()

    if transport is None:
        if not llm_config.provider:
            transport = RecordedTransport(recordings={})
        elif llm_config.provider.lower() == "openai":
            import os

            transport = OpenAIHTTPTransport(
                model=llm_config.model or "gpt-4o-mini",
                api_key=os.environ.get("OPENAI_API_KEY"),
            )
        else:
            msg = f"Unsupported LLM provider: {llm_config.provider}"
            raise ConfigurationError(msg)

    nonce = hashlib.sha256(run_ctx.run_id.encode("utf-8")).hexdigest()[:16]
    return LLMAdapter(
        config=llm_config,
        cache=cache,
        budget=budget,
        transport=transport,
        nonce=nonce,
    )
