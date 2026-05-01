import re
import uuid
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphNode
from app.providers.base import EmbeddingProvider, LLMProvider
from app.services.graph_search import GraphSearchService, Subgraph
from app.services.vector_search import SearchResult, VectorSearchService

Confidence = Literal["high", "medium", "low", "insufficient_evidence"]


class Citation(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    citation: str
    text: str


class RAGResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    retrieved_chunks: list[SearchResult] = Field(default_factory=list)
    graph_paths: list[Subgraph] = Field(default_factory=list)
    mode: str
    confidence: Confidence


class RAGService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider
        self.vector_search = VectorSearchService(db, embedding_provider)
        self.graph_search = GraphSearchService(db)

    async def query(self, user_question: str, project_id: uuid.UUID, mode: str = "single", k: int = 10) -> RAGResponse:
        if mode not in {"single", "global"}:
            raise ValueError("Use comparative_query for comparative mode with selected project_ids.")

        retrieved_chunks = await self.vector_search.search(user_question, project_id, k)
        graph_paths = await self._query_graph_context(user_question, [project_id])
        return await self._answer(user_question, retrieved_chunks, graph_paths, mode)

    async def comparative_query(self, user_question: str, project_ids: list[uuid.UUID], k: int = 10) -> RAGResponse:
        retrieved_chunks = await self.vector_search.multi_project_search(user_question, project_ids, k)
        graph_paths = await self._query_graph_context(user_question, project_ids)
        return await self._answer(user_question, retrieved_chunks, graph_paths, "comparative")

    async def _query_graph_context(self, user_question: str, project_ids: list[uuid.UUID]) -> list[Subgraph]:
        graph_paths: list[Subgraph] = []
        for project_id in project_ids:
            entity_nodes = await self._find_query_entity_nodes(user_question, project_id)
            for node in entity_nodes[:5]:
                graph_paths.append(await self.graph_search.get_neighborhood(node.id, depth=1, project_id=project_id))
        return graph_paths

    async def _find_query_entity_nodes(self, user_question: str, project_id: uuid.UUID) -> list[GraphNode]:
        result = await self.db.execute(
            select(GraphNode).where(GraphNode.project_id == project_id, GraphNode.node_type == "entity")
        )
        question_lower = user_question.lower()
        return [node for node in result.scalars().all() if node.label.lower() in question_lower]

    async def _answer(
        self,
        user_question: str,
        retrieved_chunks: list[SearchResult],
        graph_paths: list[Subgraph],
        mode: str,
    ) -> RAGResponse:
        if not retrieved_chunks:
            return RAGResponse(
                answer="The available context does not contain enough evidence to answer this question.",
                citations=[],
                retrieved_chunks=[],
                graph_paths=graph_paths,
                mode=mode,
                confidence="insufficient_evidence",
            )

        context = self._compose_context(retrieved_chunks, graph_paths, mode)
        answer = await self.llm_provider.complete(
            prompt=f"Question: {user_question}\n\nContext:\n{context}",
            system=self._system_prompt(),
        )
        valid_chunk_ids = {result.chunk_id for result in retrieved_chunks}
        cited_chunk_ids = _extract_cited_chunk_ids(answer)
        valid_cited_chunk_ids = [chunk_id for chunk_id in cited_chunk_ids if chunk_id in valid_chunk_ids]
        citations = self._build_citations(valid_cited_chunk_ids, retrieved_chunks)

        invalid_citations = [chunk_id for chunk_id in cited_chunk_ids if chunk_id not in valid_chunk_ids]
        if invalid_citations:
            answer = (
                f"{answer}\n\n"
                "Unsupported citations were removed from confidence scoring because they did not map to retrieved chunks."
            )

        return RAGResponse(
            answer=answer,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
            graph_paths=graph_paths,
            mode=mode,
            confidence=self._confidence(retrieved_chunks, citations, invalid_citations),
        )

    @staticmethod
    def _system_prompt() -> str:
        return "\n".join(
            [
                "Answer only from the provided context.",
                "Every claim must be followed by [chunk_id] citation.",
                "If the context does not support a claim, say so explicitly.",
                "Do not speculate beyond the evidence.",
                "Use exact chunk IDs from the context. Do not invent citations.",
            ]
        )

    @staticmethod
    def _compose_context(retrieved_chunks: list[SearchResult], graph_paths: list[Subgraph], mode: str) -> str:
        lines = [f"Mode: {mode}", "Retrieved chunks:"]
        if mode == "comparative":
            by_project: dict[str, list[SearchResult]] = defaultdict(list)
            for result in retrieved_chunks:
                by_project[str(result.project_id)].append(result)
            for project_id, results in by_project.items():
                lines.append(f"Project {project_id}:")
                for result in results:
                    lines.append(_chunk_context_line(result))
        else:
            for result in retrieved_chunks:
                lines.append(_chunk_context_line(result))

        lines.append("Graph summaries:")
        for index, subgraph in enumerate(graph_paths):
            node_summary = ", ".join(f"{node.node_type}:{node.label}" for node in subgraph.nodes[:10])
            edge_summary = ", ".join(
                f"{edge.edge_type}({edge.source_node_id}->{edge.target_node_id}) evidence [{edge.evidence_chunk_id}]"
                for edge in subgraph.edges[:10]
            )
            lines.append(f"Subgraph {index + 1}: nodes={node_summary}; edges={edge_summary}")
        return "\n".join(lines)

    @staticmethod
    def _build_citations(cited_chunk_ids: list[uuid.UUID], retrieved_chunks: list[SearchResult]) -> list[Citation]:
        by_chunk_id = {result.chunk_id: result for result in retrieved_chunks}
        unique_citations: list[Citation] = []
        seen: set[uuid.UUID] = set()
        for chunk_id in cited_chunk_ids:
            if chunk_id in seen or chunk_id not in by_chunk_id:
                continue
            result = by_chunk_id[chunk_id]
            seen.add(chunk_id)
            unique_citations.append(
                Citation(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    citation=result.citation,
                    text=result.text,
                )
            )
        return unique_citations

    @staticmethod
    def _confidence(
        retrieved_chunks: list[SearchResult],
        citations: list[Citation],
        invalid_citations: list[uuid.UUID],
    ) -> Confidence:
        if not retrieved_chunks or not citations:
            return "insufficient_evidence"
        if invalid_citations:
            return "low"
        top_score = max(result.similarity_score for result in retrieved_chunks)
        if top_score >= 0.85 and len(citations) >= 2:
            return "high"
        if top_score >= 0.75:
            return "medium"
        return "low"


def _chunk_context_line(result: SearchResult) -> str:
    return (
        f"[{result.chunk_id}] project={result.project_id} document={result.document_id} "
        f"citation={result.citation} score={result.similarity_score:.4f}\n{result.text}"
    )


def _extract_cited_chunk_ids(answer: str) -> list[uuid.UUID]:
    chunk_ids: list[uuid.UUID] = []
    for value in re.findall(r"\[([0-9a-fA-F-]{36})\]", answer):
        try:
            chunk_ids.append(uuid.UUID(value))
        except ValueError:
            continue
    return chunk_ids
