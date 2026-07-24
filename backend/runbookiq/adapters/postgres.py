import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from runbookiq.domain.retrieval import DocumentChunk, RankedChunk


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.9f}" for value in vector) + "]"


class PostgresKnowledgeIndex:
    """pgvector + PostgreSQL full-text adapter behind one hybrid-search interface."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def upsert_chunks(
        self,
        *,
        knowledge_base_id: str,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> None:
        statement = text(
            """
            INSERT INTO knowledge_chunks (
                id, knowledge_base_id, source_id, title, section_path, content,
                parent_content, source_url, metadata, embedding
            )
            VALUES (
                :id, :knowledge_base_id, :source_id, :title, :section_path, :content,
                :parent_content, :source_url, CAST(:metadata AS jsonb), CAST(:embedding AS vector)
            )
            ON CONFLICT (knowledge_base_id, id) DO UPDATE SET
                title = EXCLUDED.title,
                section_path = EXCLUDED.section_path,
                content = EXCLUDED.content,
                parent_content = EXCLUDED.parent_content,
                source_url = EXCLUDED.source_url,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                updated_at = now()
            """
        )
        rows = [
            {
                "id": chunk.id,
                "knowledge_base_id": knowledge_base_id,
                "source_id": chunk.source_id,
                "title": chunk.title,
                "section_path": chunk.section_path,
                "content": chunk.text,
                "parent_content": chunk.parent_text,
                "source_url": chunk.source_url,
                "metadata": json.dumps(chunk.metadata),
                "embedding": _vector_literal(embedding),
            }
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        async with self._engine.begin() as connection:
            await connection.execute(statement, rows)

    async def lexical_search(
        self,
        *,
        knowledge_base_id: str,
        queries: list[str],
        limit: int,
    ) -> list[RankedChunk]:
        query = " OR ".join(f"({item})" for item in queries)
        statement = text(
            """
            SELECT id, source_id, title, section_path, content, parent_content,
                   source_url, metadata,
                   ts_rank_cd(search_vector, websearch_to_tsquery('simple', :query)) AS score
            FROM knowledge_chunks
            WHERE knowledge_base_id = :knowledge_base_id
              AND search_vector @@ websearch_to_tsquery('simple', :query)
            ORDER BY score DESC, id
            LIMIT :limit
            """
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(
                statement,
                {
                    "knowledge_base_id": knowledge_base_id,
                    "query": query,
                    "limit": limit,
                },
            )
            rows = result.mappings().all()
        return [
            RankedChunk(
                chunk=self._row_to_chunk(row),
                rank=rank,
                score=round(float(row["score"]), 6),
            )
            for rank, row in enumerate(rows, start=1)
        ]

    async def vector_search(
        self,
        *,
        knowledge_base_id: str,
        embedding: list[float],
        limit: int,
    ) -> list[RankedChunk]:
        statement = text(
            """
            SELECT id, source_id, title, section_path, content, parent_content,
                   source_url, metadata,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM knowledge_chunks
            WHERE knowledge_base_id = :knowledge_base_id
            ORDER BY embedding <=> CAST(:embedding AS vector), id
            LIMIT :limit
            """
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(
                statement,
                {
                    "knowledge_base_id": knowledge_base_id,
                    "embedding": _vector_literal(embedding),
                    "limit": limit,
                },
            )
            rows = result.mappings().all()
        return [
            RankedChunk(
                chunk=self._row_to_chunk(row),
                rank=rank,
                score=round(float(row["score"]), 6),
            )
            for rank, row in enumerate(rows, start=1)
        ]

    @staticmethod
    def _row_to_chunk(row: dict) -> DocumentChunk:
        return DocumentChunk(
            id=row["id"],
            source_id=row["source_id"],
            title=row["title"],
            section_path=row["section_path"],
            text=row["content"],
            parent_text=row["parent_content"],
            source_url=row["source_url"],
            metadata=row["metadata"] or {},
        )
