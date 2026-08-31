from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Protocol, runtime_checkable


class RetryableError(Exception):
    """A transient transport failure that may be retried."""


class LLMTransportError(Exception):
    """A non-retryable transport failure or exhaustion of retries."""


@runtime_checkable
class Transport(Protocol):
    """Pluggable transport for a single LLM structured call."""

    async def call(
        self,
        *,
        prompt: str,
        temperature: float,
        timeout: float,
        trace: str,
    ) -> tuple[str, dict[str, object]]:
        """Issue one request and return the raw response text plus usage.

        Args:
            prompt: The fully rendered prompt text.
            temperature: Sampling temperature (always 0 for deterministic calls).
            timeout: Wall-clock timeout in seconds.
            trace: Logical trace identifier for the call.

        Returns:
            Tuple of ``(raw_response_text, usage_dict)``.

        Raises:
            RetryableError: for transient failures that may be retried.
            LLMTransportError: for permanent failures.
        """
        ...


class RecordedTransport(Transport):
    """Transport that replays canned responses for tests.

    This transport never makes a network call.  Recordings are keyed by the
    *trace* identifier passed to the adapter, which makes tests deterministic and
    fast.

    Attributes:
        recordings: Mapping from trace to ``(raw_response, usage_dict)``.
        failures: Mapping from trace to the exception to raise.
    """

    def __init__(
        self,
        recordings: Mapping[str, tuple[str, dict[str, object]]],
        failures: Mapping[str, Exception] | None = None,
    ) -> None:
        self._recordings = dict(recordings)
        self._failures = dict(failures or {})

    async def call(
        self,
        *,
        prompt: str,
        temperature: float,
        timeout: float,
        trace: str,
    ) -> tuple[str, dict[str, object]]:
        """Return a recorded response or raise a configured failure."""
        if trace in self._failures:
            raise self._failures[trace]
        if trace not in self._recordings:
            msg = f"No recorded response for trace {trace!r}"
            raise LLMTransportError(msg)
        return self._recordings[trace]


class OpenAIHTTPTransport(Transport):
    """OpenAI-compatible HTTP transport using only the Python stdlib.

    The provider SDK is imported lazily inside the call method; at module scope
    only stdlib modules are referenced.  This keeps the adapter provider-agnostic:
    swapping the transport implementation changes the provider.

    Attributes:
        model: Model identifier to request.
        api_key: API key or ``None``.
        base_url: Provider base URL.
        timeout: Default request timeout.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 90.0,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def call(
        self,
        *,
        prompt: str,
        temperature: float,
        timeout: float,
        trace: str,
    ) -> tuple[str, dict[str, object]]:
        """POST to the chat completions endpoint and parse the response."""
        import urllib.error
        import urllib.request

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or ''}",
        }
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")

        def _sync_call() -> tuple[str, dict[str, object]]:
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 502, 503, 504):
                    raise RetryableError(f"HTTP {exc.code}: {exc.reason}") from exc
                raise LLMTransportError(f"HTTP {exc.code}: {exc.reason}") from exc
            except urllib.error.URLError as exc:
                raise RetryableError(f"Network error: {exc.reason}") from exc
            except TimeoutError as exc:
                raise RetryableError("Request timed out") from exc

            choice = body["choices"][0]
            content = choice["message"]["content"]
            usage = body.get("usage", {})
            return content, {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }

        return await asyncio.to_thread(_sync_call)


class FireworksAIHTTPTransport(OpenAIHTTPTransport):
    """Fireworks AI HTTP transport (OpenAI-compatible).

    Uses Fireworks AI's inference endpoint. Defaults to the Fireworks AI
    base URL and reads the API key from the FIREWORKS_API_KEY environment
    variable if not provided explicitly.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://api.fireworks.ai/inference/v1",
        timeout: float = 90.0,
    ) -> None:
        import os

        if api_key is None:
            api_key = os.environ.get("FIREWORKS_API_KEY")
        super().__init__(model=model, api_key=api_key, base_url=base_url, timeout=timeout)
