from __future__ import annotations

import hashlib
import math

from app.providers.base import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for offline local smoke tests."""

    model = "local-hash-embedding-1536"

    async def embed_text(self, text: str) -> list[float]:
        return _embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [_embed(text) for text in texts]


def _embed(text: str) -> list[float]:
    vector = [0.0] * 1536
    tokens = [token.strip(".,;:!?()[]{}\"'").lower() for token in text.split()]
    for token in tokens:
        if not token:
            continue
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % len(vector)
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
