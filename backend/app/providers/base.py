from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class EmbeddingProvider(ABC):
    """Provider interface for text embeddings."""

    model: str

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text value."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text values."""


class LLMProvider(ABC):
    """Provider interface for language model completion and streaming."""

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Return a complete text response."""

    @abstractmethod
    async def stream(self, prompt: str, system: str | None = None) -> AsyncIterator[str]:
        """Yield text response chunks."""
