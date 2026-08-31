from __future__ import annotations

from resume_ranker.embeddings.client import (
    HostedEmbeddingClient,
    LocalEmbeddingClient,
    create_embedding_client,
)

__all__ = [
    "HostedEmbeddingClient",
    "LocalEmbeddingClient",
    "create_embedding_client",
]
