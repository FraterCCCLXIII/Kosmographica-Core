from __future__ import annotations

import hashlib
import math
import re
from collections.abc import AsyncIterator

from app.providers.base import EmbeddingProvider, LLMProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for offline local smoke tests."""

    model = "local-hash-embedding-1536"

    async def embed_text(self, text: str) -> list[float]:
        return _embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [_embed(text) for text in texts]


class LocalLLMProvider(LLMProvider):
    """Local RAG verifier that only echoes retrieved evidence with citations."""

    model = "local-verbatim-rag"
    is_local = True

    async def complete(self, prompt: str, system: str | None = None) -> str:
        chunks = _extract_prompt_chunks(prompt)
        return "\n\n".join(f"{text} [{chunk_id}]" for chunk_id, text in chunks)

    async def stream(self, prompt: str, system: str | None = None) -> AsyncIterator[str]:
        yield await self.complete(prompt, system)


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


def _extract_prompt_chunks(prompt: str) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    lines = prompt.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"\[([0-9a-fA-F-]{36})\].*", line)
        if not match:
            continue
        text = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if text:
            chunks.append((match.group(1), text))
    return chunks
