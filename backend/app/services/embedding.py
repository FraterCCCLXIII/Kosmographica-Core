import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk as ChunkModel
from app.models.document import ChunkEmbedding
from app.providers.base import EmbeddingProvider


class EmbeddingService:
    def __init__(self, db: AsyncSession, max_concurrency: int = 4) -> None:
        self.db = db
        self.max_concurrency = max_concurrency

    async def embed_chunk(self, chunk_id: uuid.UUID, provider: EmbeddingProvider) -> ChunkEmbedding | None:
        model = self._provider_model(provider)
        provider_name = self._provider_name(provider)
        existing_embedding = await self._get_existing_embedding(chunk_id, provider_name, model)
        if existing_embedding:
            return existing_embedding

        chunk = await self.db.get(ChunkModel, chunk_id)
        if not chunk:
            raise ValueError(f"Chunk not found: {chunk_id}")

        vector = await provider.embed_text(chunk.text)
        embedding = ChunkEmbedding(
            chunk_id=chunk.id,
            provider=provider_name,
            model=model,
            embedding=vector,
        )
        self.db.add(embedding)
        await self.db.commit()
        await self.db.refresh(embedding)
        return embedding

    async def embed_document(self, document_id: uuid.UUID, provider: EmbeddingProvider) -> list[ChunkEmbedding]:
        result = await self.db.execute(
            select(ChunkModel.id)
            .where(ChunkModel.document_id == document_id)
            .order_by(ChunkModel.chunk_index)
        )
        chunk_ids = list(result.scalars().all())
        return await self.embed_batch(chunk_ids, provider)

    async def embed_batch(self, chunk_ids: list[uuid.UUID], provider: EmbeddingProvider) -> list[ChunkEmbedding]:
        model = self._provider_model(provider)
        provider_name = self._provider_name(provider)
        chunks_to_embed: list[ChunkModel] = []
        for chunk_id in chunk_ids:
            if await self._get_existing_embedding(chunk_id, provider_name, model):
                continue
            chunk = await self.db.get(ChunkModel, chunk_id)
            if chunk:
                chunks_to_embed.append(chunk)

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def embed_with_limit(chunk: ChunkModel) -> tuple[uuid.UUID, list[float]]:
            async with semaphore:
                return chunk.id, await provider.embed_text(chunk.text)

        embedded_vectors = await asyncio.gather(*(embed_with_limit(chunk) for chunk in chunks_to_embed))
        embeddings = [
            ChunkEmbedding(chunk_id=chunk_id, provider=provider_name, model=model, embedding=vector)
            for chunk_id, vector in embedded_vectors
        ]
        self.db.add_all(embeddings)
        await self.db.commit()
        for embedding in embeddings:
            await self.db.refresh(embedding)
        return embeddings

    async def _get_existing_embedding(
        self,
        chunk_id: uuid.UUID,
        provider_name: str,
        model: str,
    ) -> ChunkEmbedding | None:
        result = await self.db.execute(
            select(ChunkEmbedding).where(
                ChunkEmbedding.chunk_id == chunk_id,
                ChunkEmbedding.provider == provider_name,
                ChunkEmbedding.model == model,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _provider_model(provider: EmbeddingProvider) -> str:
        return str(getattr(provider, "model", "unknown"))

    @staticmethod
    def _provider_name(provider: EmbeddingProvider) -> str:
        class_name = provider.__class__.__name__.lower()
        if "openai" in class_name:
            return "openai"
        return class_name.replace("embeddingprovider", "")
