import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import tiktoken


@dataclass(frozen=True)
class ChunkingConfig:
    chunk_size: int = 800
    chunk_overlap: int = 100
    strategy: str = "sentence"

    @classmethod
    def from_mapping(cls, config: dict[str, Any] | None) -> "ChunkingConfig":
        config = config or {}
        return cls(
            chunk_size=max(1, int(config.get("chunk_size", cls.chunk_size))),
            chunk_overlap=max(0, int(config.get("chunk_overlap", cls.chunk_overlap))),
            strategy=str(config.get("strategy", cls.strategy)),
        )


@dataclass(frozen=True)
class Chunk:
    project_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    token_count: int
    citation: str
    char_start: int
    char_end: int
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkingService:
    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self.encoding = tiktoken.get_encoding(encoding_name)

    def chunk(
        self,
        text: str,
        config: dict[str, Any] | ChunkingConfig | None,
        *,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        citation_prefix: str | None = None,
    ) -> list[Chunk]:
        chunking_config = config if isinstance(config, ChunkingConfig) else ChunkingConfig.from_mapping(config)
        if chunking_config.chunk_overlap >= chunking_config.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if chunking_config.strategy == "fixed":
            return self._chunk_fixed(text, chunking_config, project_id, document_id, citation_prefix)
        if chunking_config.strategy == "sentence":
            return self._chunk_sentence(text, chunking_config, project_id, document_id, citation_prefix)
        raise ValueError(f"Unsupported chunking strategy: {chunking_config.strategy}")

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def _chunk_fixed(
        self,
        text: str,
        config: ChunkingConfig,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        citation_prefix: str | None,
    ) -> list[Chunk]:
        tokens = self.encoding.encode(text)
        chunks: list[Chunk] = []
        start_token = 0
        while start_token < len(tokens):
            end_token = min(start_token + config.chunk_size, len(tokens))
            chunk_text = self.encoding.decode(tokens[start_token:end_token]).strip()
            if chunk_text:
                chunks.append(self._build_chunk(chunks, text, chunk_text, project_id, document_id, citation_prefix))
            if end_token == len(tokens):
                break
            start_token = end_token - config.chunk_overlap
        return chunks

    def _chunk_sentence(
        self,
        text: str,
        config: ChunkingConfig,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        citation_prefix: str | None,
    ) -> list[Chunk]:
        sentences = self._split_sentences(text)
        chunks: list[Chunk] = []
        current_sentences: list[str] = []
        current_tokens = 0
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            if current_sentences and current_tokens + sentence_tokens > config.chunk_size:
                chunks.append(self._build_chunk(chunks, text, " ".join(current_sentences), project_id, document_id, citation_prefix))
                current_sentences, current_tokens = self._overlap_sentences(current_sentences, config.chunk_overlap)
            current_sentences.append(sentence)
            current_tokens += sentence_tokens
        if current_sentences:
            chunks.append(self._build_chunk(chunks, text, " ".join(current_sentences), project_id, document_id, citation_prefix))
        return chunks

    def _build_chunk(
        self,
        existing_chunks: list[Chunk],
        full_text: str,
        chunk_text: str,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        citation_prefix: str | None,
    ) -> Chunk:
        chunk_index = len(existing_chunks)
        search_start = existing_chunks[-1].char_end if existing_chunks else 0
        char_start = full_text.find(chunk_text, max(0, search_start - 500))
        if char_start == -1:
            char_start = search_start
        char_end = char_start + len(chunk_text)
        citation_base = citation_prefix or f"document:{document_id}"
        return Chunk(
            project_id=project_id,
            document_id=document_id,
            chunk_index=chunk_index,
            text=chunk_text,
            token_count=self.count_tokens(chunk_text),
            citation=f"{citation_base}#chunk-{chunk_index}",
            char_start=char_start,
            char_end=char_end,
            metadata={"char_start": char_start, "char_end": char_end, "strategy": "chunking"},
        )

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]

    def _overlap_sentences(self, sentences: list[str], overlap_tokens: int) -> tuple[list[str], int]:
        if overlap_tokens <= 0:
            return [], 0
        selected: list[str] = []
        total_tokens = 0
        for sentence in reversed(sentences):
            sentence_tokens = self.count_tokens(sentence)
            if selected and total_tokens + sentence_tokens > overlap_tokens:
                break
            selected.insert(0, sentence)
            total_tokens += sentence_tokens
        return selected, total_tokens
