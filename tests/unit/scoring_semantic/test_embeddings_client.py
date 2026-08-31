from __future__ import annotations

import asyncio

import numpy as np
import pytest

from resume_ranker.embeddings.client import (
    HostedEmbeddingClient,
    LocalEmbeddingClient,
    create_embedding_client,
)
from resume_ranker.models.config import EmbeddingConfig
from resume_ranker.protocols import EmbeddingClient


class FakeSentenceTransformer:
    """Minimal stand-in for ``sentence_transformers.SentenceTransformer``."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.call_count = 0
        self.last_batch: list[str] | None = None

    def encode(self, texts: list[str], *, convert_to_numpy: bool = True) -> np.ndarray:
        self.call_count += 1
        self.last_batch = list(texts)
        vectors = np.zeros((len(texts), 384), dtype=np.float64)
        for i, text in enumerate(texts):
            vectors[i, 0] = float(len(text))
        return vectors


@pytest.fixture
def patch_transformer(monkeypatch: pytest.MonkeyPatch) -> FakeSentenceTransformer:
    fake = FakeSentenceTransformer("all-MiniLM-L6-v2")
    monkeypatch.setattr(
        "resume_ranker.embeddings.client.SentenceTransformer",
        lambda model_name: fake,
    )
    return fake


def test_local_embedding_client_satisfies_protocol(
    patch_transformer: FakeSentenceTransformer,
) -> None:
    client = LocalEmbeddingClient(model="all-MiniLM-L6-v2")
    assert isinstance(client, EmbeddingClient)
    assert client.dimensions == 384
    vectors = asyncio.run(client.embed(["hello", "world"]))
    assert len(vectors) == 2
    assert all(len(v) == 384 for v in vectors)
    assert patch_transformer.call_count == 1


def test_local_embedding_client_caches(
    patch_transformer: FakeSentenceTransformer,
) -> None:
    client = LocalEmbeddingClient(model="all-MiniLM-L6-v2", cache=True)
    v1 = asyncio.run(client.embed(["repeat"]))
    v2 = asyncio.run(client.embed(["repeat"]))
    assert v1 == v2
    assert patch_transformer.call_count == 1


def test_local_embedding_client_batches(
    patch_transformer: FakeSentenceTransformer,
) -> None:
    client = LocalEmbeddingClient(model="all-MiniLM-L6-v2", batch_size=2)
    texts = ["a", "b", "c", "d", "e"]
    asyncio.run(client.embed(texts))
    assert patch_transformer.call_count == 3  # 2, 2, 1


def test_local_embedding_client_order_preserved(
    patch_transformer: FakeSentenceTransformer,
) -> None:
    client = LocalEmbeddingClient(model="all-MiniLM-L6-v2", batch_size=2)
    texts = ["first", "second", "third"]
    vectors = asyncio.run(client.embed(texts))
    assert len(vectors) == len(texts)
    assert vectors[0][0] == float(len("first"))
    assert vectors[1][0] == float(len("second"))
    assert vectors[2][0] == float(len("third"))


def test_create_embedding_client_local() -> None:
    config = EmbeddingConfig(local=True, model="all-MiniLM-L6-v2", batch_size=16)
    client = create_embedding_client(config)
    assert isinstance(client, LocalEmbeddingClient)
    assert client.batch_size == 16


def test_create_embedding_client_hosted() -> None:
    config = EmbeddingConfig(local=False, model="hosted-model", batch_size=8)
    client = create_embedding_client(config)
    assert isinstance(client, HostedEmbeddingClient)
    assert client.model == "hosted-model"
    assert client.dimensions == 384


def test_hosted_embedding_client_not_implemented() -> None:
    client = HostedEmbeddingClient(model="hosted-model", dimensions=384)
    with pytest.raises(NotImplementedError):
        asyncio.run(client.embed(["hello"]))
