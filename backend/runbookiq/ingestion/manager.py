import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from runbookiq.domain.models import IngestionJob, SourceDocument
from runbookiq.domain.retrieval import DocumentChunk
from runbookiq.ingestion.chunker import ParentChildChunker
from runbookiq.ingestion.parser import DocumentParser

logger = logging.getLogger(__name__)


class ChunkEmbedder(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class KnowledgeWriter(Protocol):
    async def stage_object(self, storage_key: str) -> None: ...

    async def replace_document(
        self,
        *,
        document: SourceDocument,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> str | None: ...

    async def get_document(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> SourceDocument: ...

    async def find_document_by_checksum(
        self,
        *,
        knowledge_base_id: str,
        checksum: str,
    ) -> SourceDocument | None: ...

    async def list_documents(self, knowledge_base_id: str) -> list[SourceDocument]: ...

    async def delete_document(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> SourceDocument: ...

    async def list_pending_object_deletions(self) -> list[str]: ...

    async def confirm_object_deletion(self, storage_key: str) -> None: ...


class DocumentStore(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


_TEXT_SUFFIXES = {
    ".csv",
    ".htm",
    ".html",
    ".json",
    ".markdown",
    ".md",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
_TEXT_CONTENT_TYPES = {
    "application/json",
    "application/xml",
    "application/yaml",
}


def _canonical_source_bytes(
    *,
    filename: str,
    content_type: str,
    content: bytes,
) -> bytes:
    suffix = Path(filename).suffix.lower()
    is_text = (
        content_type.startswith("text/")
        or content_type in _TEXT_CONTENT_TYPES
        or suffix in _TEXT_SUFFIXES
    )
    if not is_text:
        return content
    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


class InlineIngestionManager:
    """Local adapter that executes the ingestion module inline."""

    def __init__(
        self,
        *,
        parser: DocumentParser,
        chunker: ParentChildChunker,
        embedder: ChunkEmbedder,
        writer: KnowledgeWriter,
        object_store: DocumentStore,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._writer = writer
        self._object_store = object_store
        self._jobs: dict[str, IngestionJob] = {}
        self._submit_locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._document_locks: dict[tuple[str, str], asyncio.Lock] = {}

    async def submit(
        self,
        *,
        knowledge_base_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> IngestionJob:
        identity_bytes = _canonical_source_bytes(
            filename=filename,
            content_type=content_type,
            content=content,
        )
        checksum = hashlib.sha256(identity_bytes).hexdigest()
        lock = self._submit_locks.setdefault(
            (knowledge_base_id, checksum),
            asyncio.Lock(),
        )
        async with lock:
            duplicate = await self._writer.find_document_by_checksum(
                knowledge_base_id=knowledge_base_id,
                checksum=checksum,
            )
            if duplicate is not None:
                return self._completed_job(document=duplicate, filename=filename)
            document_id = f"doc-{uuid4().hex}"
            return await self._ingest(
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                source_id=f"src-{checksum[:16]}",
                version=1,
                created_at=datetime.now(UTC).isoformat(),
                filename=filename,
                content_type=content_type,
                content=content,
                checksum=checksum,
            )

    async def replace(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> IngestionJob:
        lock = self._document_locks.setdefault(
            (knowledge_base_id, document_id),
            asyncio.Lock(),
        )
        async with lock:
            current = await self._writer.get_document(
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
            )
            identity_bytes = _canonical_source_bytes(
                filename=filename,
                content_type=content_type,
                content=content,
            )
            checksum = hashlib.sha256(identity_bytes).hexdigest()
            if checksum == current.checksum:
                return self._completed_job(document=current, filename=filename)
            return await self._ingest(
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                source_id=current.source_id,
                version=current.version + 1,
                created_at=current.created_at,
                filename=filename,
                content_type=content_type,
                content=content,
                checksum=checksum,
            )

    async def _ingest(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
        source_id: str,
        version: int,
        created_at: str,
        filename: str,
        content_type: str,
        content: bytes,
        checksum: str,
    ) -> IngestionJob:
        job_id = f"job-{uuid4().hex[:12]}"
        job = IngestionJob(
            id=job_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            filename=filename,
            status="processing",
            progress=10,
        )
        self._jobs[job_id] = job
        try:
            sections = self._parser.parse(
                filename=filename,
                content_type=content_type,
                content=content,
            )
            chunks = self._chunker.chunk(
                source_id=source_id,
                source_url=f"upload://{filename}",
                sections=sections,
            )
            if not chunks:
                raise ValueError("document does not contain indexable text")
            embeddings = await self._embedder.embed_documents(
                [chunk.text for chunk in chunks]
            )
            suffix = Path(filename).suffix.lower()
            storage_key = (
                f"{knowledge_base_id}/{document_id}/v{version}-{job_id}/original{suffix}"
            )
            await self._writer.stage_object(storage_key)
            try:
                await self._object_store.put(storage_key, content, content_type)
            except Exception:
                await self._cleanup_object(storage_key)
                raise
            updated_at = datetime.now(UTC).isoformat()
            document = SourceDocument(
                id=document_id,
                knowledge_base_id=knowledge_base_id,
                source_id=source_id,
                filename=filename,
                content_type=content_type,
                size_bytes=len(content),
                checksum=checksum,
                version=version,
                chunks_count=len(chunks),
                original_available=True,
                created_at=created_at,
                updated_at=updated_at,
                storage_key=storage_key,
            )
            try:
                previous_storage_key = await self._writer.replace_document(
                    document=document,
                    chunks=chunks,
                    embeddings=embeddings,
                )
            except Exception:
                await self._cleanup_object(storage_key)
                raise
            if previous_storage_key and previous_storage_key != storage_key:
                await self._cleanup_object(previous_storage_key)
            job = job.model_copy(
                update={
                    "status": "completed",
                    "progress": 100,
                    "chunks_created": len(chunks),
                }
            )
        except Exception as exc:
            logger.exception(
                "document ingestion failed",
                extra={
                    "knowledge_base_id": knowledge_base_id,
                    "document_id": document_id,
                    "source_filename": filename,
                },
            )
            job = job.model_copy(
                update={
                    "status": "failed",
                    "progress": 100,
                    "error": str(exc),
                }
            )
        self._jobs[job_id] = job
        return job

    def _completed_job(
        self,
        *,
        document: SourceDocument,
        filename: str,
    ) -> IngestionJob:
        job = IngestionJob(
            id=f"job-{uuid4().hex[:12]}",
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            filename=filename,
            status="completed",
            progress=100,
            chunks_created=document.chunks_count,
        )
        self._jobs[job.id] = job
        return job

    async def list_documents(self, knowledge_base_id: str) -> list[SourceDocument]:
        await self._retry_pending_object_deletions()
        return await self._writer.list_documents(knowledge_base_id)

    async def cleanup_pending_objects(self) -> None:
        await self._retry_pending_object_deletions()

    async def delete_document(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> None:
        deleted = await self._writer.delete_document(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
        if deleted.storage_key:
            await self._cleanup_object(deleted.storage_key)

    async def _retry_pending_object_deletions(self) -> None:
        for storage_key in await self._writer.list_pending_object_deletions():
            await self._cleanup_object(storage_key)

    async def _cleanup_object(self, storage_key: str) -> None:
        try:
            await self._object_store.delete(storage_key)
        except Exception:
            logger.exception("document object cleanup remains queued for retry")
            return
        await self._writer.confirm_object_deletion(storage_key)

    async def get_document_content(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> tuple[SourceDocument, bytes]:
        document = await self._writer.get_document(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
        if not document.storage_key:
            raise FileNotFoundError(document_id)
        try:
            content = await self._object_store.get(document.storage_key)
        except KeyError as exc:
            raise FileNotFoundError(document_id) from exc
        return document, content

    async def get_job(self, job_id: str) -> IngestionJob:
        return self._jobs[job_id]
