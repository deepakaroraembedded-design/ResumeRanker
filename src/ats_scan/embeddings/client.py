from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from ats_scan.models.config import EmbeddingConfig
from ats_scan.models.embeddings import Vector
from ats_scan.protocols import EmbeddingClient


class LocalEmbeddingClient:
    """Local sentence-transformer embedding client (TRD §14).

    The default model is the Qwen 8B embedding model installed on the host; the
    older ``all-MiniLM-L6-v2`` model remains selectable via configuration.  Qwen
    models are loaded with ``trust_remote_code=True`` and placed on the fastest
    available accelerator.  The model is loaded lazily on the first ``embed``
    call and inference is run in a worker thread so the async API remains
    non-blocking.  Embeddings are cached by SHA-256 of the input text and batched
    according to the configured batch size.
    """

    dimensions: int = 384

    def __init__(
        self,
        model: str | None = None,
        batch_size: int = 64,
        *,
        cache: bool = True,
        device: str | None = None,
        model_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._model_name = model or "Qwen/Qwen3-Embedding-8B"
        self.batch_size = batch_size
        self._cache: dict[str, Vector] | None = {} if cache else None
        self._model: SentenceTransformer | None = None
        self._device = device
        self._model_kwargs = model_kwargs or {}
        if "qwen" in self._model_name.lower():
            self.dimensions = 4096

    def _resolve_device(self) -> str:
        if self._device:
            return self._device
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            kwargs: dict[str, Any] = dict(self._model_kwargs)
            if "qwen" in self._model_name.lower():
                kwargs.setdefault("trust_remote_code", True)
                kwargs.setdefault("device", self._resolve_device())
            self._model = SentenceTransformer(self._model_name, **kwargs)
            if hasattr(self._model, "get_embedding_dimension"):
                self.dimensions = cast(int, self._model.get_embedding_dimension())
            elif hasattr(self._model, "get_sentence_embedding_dimension"):
                self.dimensions = cast(int, self._model.get_sentence_embedding_dimension())
        return self._model

    def model_identifier(self) -> str:
        """Return a pinned model identifier: name + HF cache snapshot hash.

        The snapshot hash is the exact revision the local cache is using, so the
        identifier is reproducible across runs as long as the cached model files
        are not replaced.
        """
        model = self._load_model()
        vocab_file = getattr(model.tokenizer, "vocab_file", None)
        if not isinstance(vocab_file, str):
            return self._model_name
        snapshot = Path(vocab_file).parent.name
        return f"{self._model_name}@{snapshot}"

    async def _encode(self, texts: Sequence[str]) -> Sequence[Vector]:
        model = self._load_model()
        embeddings = await asyncio.to_thread(
            model.encode,
            list(texts),
            convert_to_numpy=True,
        )
        array = np.asarray(embeddings, dtype=np.float64)
        return [tuple(float(value) for value in row) for row in array]

    async def embed(self, texts: Sequence[str]) -> Sequence[Vector]:
        """Return a vector for each text, using the cache and batch size."""
        if not texts:
            return []

        ordered_hashes: list[str] = []
        missing: dict[str, str] = {}
        for text in texts:
            key = hashlib.sha256(text.encode("utf-8")).hexdigest()
            ordered_hashes.append(key)
            if self._cache is not None and key not in self._cache:
                missing[key] = text

        if missing:
            items = list(missing.items())
            for i in range(0, len(items), self.batch_size):
                batch = items[i : i + self.batch_size]
                batch_texts = [text for _key, text in batch]
                vectors = await self._encode(batch_texts)
                for (key, _), vector in zip(batch, vectors, strict=True):
                    if self._cache is not None:
                        self._cache[key] = vector

        if self._cache is not None:
            return [self._cache[key] for key in ordered_hashes]
        # Caching disabled: encode all texts in one batch and return directly.
        return await self._encode(texts)


class HostedEmbeddingClient:
    """Optional hosted embedding client placeholder behind ``EmbeddingClient``."""

    def __init__(
        self,
        model: str,
        dimensions: int,
        endpoint: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self.endpoint = endpoint
        self.api_key = api_key

    def model_identifier(self) -> str:
        """Return the configured hosted model name as the identifier."""
        return self.model

    async def embed(self, texts: Sequence[str]) -> Sequence[Vector]:
        """Not implemented; the default deployment uses the local model."""
        raise NotImplementedError("Hosted embedding calls are not implemented in this component")


def create_embedding_client(config: EmbeddingConfig) -> EmbeddingClient:
    """Factory that selects the local or hosted client based on configuration."""
    if config.local:
        return LocalEmbeddingClient(model=config.model, batch_size=config.batch_size)
    return HostedEmbeddingClient(
        model=config.model or "unknown",
        dimensions=384,
        endpoint=None,
    )
