import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from runbookiq.domain.models import SourceDocument
from runbookiq.domain.retrieval import DocumentChunk, RankedChunk


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.9f}" for value in vector) + "]"


class PostgresKnowledgeIndex:
    """pgvector + PostgreSQL full-text adapter behind one hybrid-search interface."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def stage_object(self, storage_key: str) -> None:
        statement = text(
            """
            INSERT INTO knowledge_document_object_gc (storage_key, delete_after)
            VALUES (:storage_key, now() + interval '1 hour')
            ON CONFLICT (storage_key) DO UPDATE
            SET queued_at = now(), delete_after = EXCLUDED.delete_after
            """
        )
        async with self._engine.begin() as connection:
            await connection.execute(statement, {"storage_key": storage_key})

    async def replace_document(
        self,
        *,
        document: SourceDocument,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> str | None:
        select_current = text(
            """
            SELECT storage_key, version
            FROM knowledge_documents
            WHERE id = :id AND knowledge_base_id = :knowledge_base_id
            FOR UPDATE
            """
        )
        upsert_document = text(
            """
            INSERT INTO knowledge_documents (
                id, knowledge_base_id, source_id, filename, content_type,
                size_bytes, checksum, storage_key, version, status, chunks_count,
                created_at, updated_at
            ) VALUES (
                :id, :knowledge_base_id, :source_id, :filename, :content_type,
                :size_bytes, :checksum, :storage_key, :version, 'ready', :chunks_count,
                CAST(:created_at AS timestamptz), CAST(:updated_at AS timestamptz)
            )
            ON CONFLICT (id) DO UPDATE SET
                filename = EXCLUDED.filename,
                content_type = EXCLUDED.content_type,
                size_bytes = EXCLUDED.size_bytes,
                checksum = EXCLUDED.checksum,
                storage_key = EXCLUDED.storage_key,
                version = EXCLUDED.version,
                status = EXCLUDED.status,
                chunks_count = EXCLUDED.chunks_count,
                updated_at = EXCLUDED.updated_at
            WHERE knowledge_documents.knowledge_base_id = EXCLUDED.knowledge_base_id
            """
        )
        delete_chunks = text(
            "DELETE FROM knowledge_chunks WHERE document_id = :document_id"
        )
        queue_object_deletion = text(
            """
            INSERT INTO knowledge_document_object_gc (storage_key)
            VALUES (:storage_key)
            ON CONFLICT (storage_key) DO NOTHING
            """
        )
        insert_chunks = text(
            """
            INSERT INTO knowledge_chunks (
                id, knowledge_base_id, document_id, source_id, title, section_path,
                content, parent_content, source_url, metadata, embedding
            ) VALUES (
                :id, :knowledge_base_id, :document_id, :source_id, :title,
                :section_path, :content, :parent_content, :source_url,
                CAST(:metadata AS jsonb), CAST(:embedding AS vector)
            )
            """
        )
        insert_checksum_alias = text(
            """
            INSERT INTO knowledge_document_checksums (
                knowledge_base_id, checksum, document_id
            ) VALUES (
                :knowledge_base_id, :checksum, :id
            )
            ON CONFLICT (knowledge_base_id, checksum) DO NOTHING
            """
        )
        select_checksum_alias = text(
            """
            SELECT document_id
            FROM knowledge_document_checksums
            WHERE knowledge_base_id = :knowledge_base_id AND checksum = :checksum
            """
        )
        activate_object = text(
            "DELETE FROM knowledge_document_object_gc WHERE storage_key = :storage_key"
        )
        document_values = {
            "id": document.id,
            "knowledge_base_id": document.knowledge_base_id,
            "source_id": document.source_id,
            "filename": document.filename,
            "content_type": document.content_type,
            "size_bytes": document.size_bytes,
            "checksum": document.checksum,
            "storage_key": document.storage_key,
            "version": document.version,
            "chunks_count": document.chunks_count,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        }
        chunk_rows = [
            {
                "id": chunk.id,
                "knowledge_base_id": document.knowledge_base_id,
                "document_id": document.id,
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
            current = (
                await connection.execute(select_current, document_values)
            ).mappings().first()
            if current is None and document.version != 1:
                raise RuntimeError("document version changed; retry replacement")
            if current is not None and document.version != current["version"] + 1:
                raise RuntimeError("document version changed; retry replacement")
            if (
                current
                and current["storage_key"]
                and current["storage_key"] != document.storage_key
            ):
                await connection.execute(
                    queue_object_deletion,
                    {"storage_key": current["storage_key"]},
                )
            await connection.execute(upsert_document, document_values)
            await connection.execute(insert_checksum_alias, document_values)
            mapped_document_id = (
                await connection.execute(select_checksum_alias, document_values)
            ).scalar_one()
            if mapped_document_id != document.id:
                raise RuntimeError("document checksum is already assigned")
            await connection.execute(delete_chunks, {"document_id": document.id})
            await connection.execute(insert_chunks, chunk_rows)
            if document.storage_key:
                await connection.execute(
                    activate_object,
                    {"storage_key": document.storage_key},
                )
        return current["storage_key"] if current else None

    async def get_document(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> SourceDocument:
        statement = text(
            """
            SELECT * FROM knowledge_documents
            WHERE knowledge_base_id = :knowledge_base_id AND id = :document_id
            """
        )
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    statement,
                    {
                        "knowledge_base_id": knowledge_base_id,
                        "document_id": document_id,
                    },
                )
            ).mappings().first()
        if row is None:
            raise KeyError(document_id)
        return self._row_to_document(row)

    async def find_document_by_checksum(
        self,
        *,
        knowledge_base_id: str,
        checksum: str,
    ) -> SourceDocument | None:
        statement = text(
            """
            SELECT documents.*
            FROM knowledge_document_checksums AS checksums
            JOIN knowledge_documents AS documents
              ON documents.knowledge_base_id = checksums.knowledge_base_id
             AND documents.id = checksums.document_id
            WHERE checksums.knowledge_base_id = :knowledge_base_id
              AND checksums.checksum = :checksum
            """
        )
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    statement,
                    {"knowledge_base_id": knowledge_base_id, "checksum": checksum},
                )
            ).mappings().first()
        return self._row_to_document(row) if row else None

    async def list_documents(self, knowledge_base_id: str) -> list[SourceDocument]:
        statement = text(
            """
            SELECT * FROM knowledge_documents
            WHERE knowledge_base_id = :knowledge_base_id
            ORDER BY updated_at DESC, id
            """
        )
        async with self._engine.connect() as connection:
            rows = (
                await connection.execute(
                    statement,
                    {"knowledge_base_id": knowledge_base_id},
                )
            ).mappings().all()
        return [self._row_to_document(row) for row in rows]

    async def delete_document(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> SourceDocument:
        statement = text(
            """
            DELETE FROM knowledge_documents
            WHERE knowledge_base_id = :knowledge_base_id AND id = :document_id
            RETURNING *
            """
        )
        async with self._engine.begin() as connection:
            row = (
                await connection.execute(
                    statement,
                    {
                        "knowledge_base_id": knowledge_base_id,
                        "document_id": document_id,
                    },
                )
            ).mappings().first()
            if row and row["storage_key"]:
                await connection.execute(
                    text(
                        """
                        INSERT INTO knowledge_document_object_gc (storage_key)
                        VALUES (:storage_key)
                        ON CONFLICT (storage_key) DO NOTHING
                        """
                    ),
                    {"storage_key": row["storage_key"]},
                )
        if row is None:
            raise KeyError(document_id)
        return self._row_to_document(row)

    async def list_pending_object_deletions(self) -> list[str]:
        statement = text(
            """
            SELECT storage_key
            FROM knowledge_document_object_gc
            WHERE delete_after <= now()
            ORDER BY queued_at, storage_key
            LIMIT 100
            """
        )
        async with self._engine.connect() as connection:
            rows = (await connection.execute(statement)).mappings().all()
        return [row["storage_key"] for row in rows]

    async def confirm_object_deletion(self, storage_key: str) -> None:
        statement = text(
            "DELETE FROM knowledge_document_object_gc WHERE storage_key = :storage_key"
        )
        async with self._engine.begin() as connection:
            await connection.execute(statement, {"storage_key": storage_key})

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

    @staticmethod
    def _row_to_document(row: dict) -> SourceDocument:
        storage_key = row["storage_key"]
        return SourceDocument(
            id=row["id"],
            knowledge_base_id=row["knowledge_base_id"],
            source_id=row["source_id"],
            filename=row["filename"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            checksum=row["checksum"],
            version=row["version"],
            status=row["status"],
            chunks_count=row["chunks_count"],
            original_available=bool(storage_key),
            created_at=row["created_at"].isoformat(),
            updated_at=row["updated_at"].isoformat(),
            storage_key=storage_key,
        )
