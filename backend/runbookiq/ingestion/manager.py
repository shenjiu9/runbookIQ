import hashlib
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from runbookiq.domain.models import IngestionJob
from runbookiq.domain.retrieval import DocumentChunk
from runbookiq.ingestion.chunker import ParentChildChunker
from runbookiq.ingestion.parser import DocumentParser


class ChunkEmbedder(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class KnowledgeWriter(Protocol):
    async def upsert_chunks(
        self,
        *,
        knowledge_base_id: str,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> None: ...


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
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._writer = writer
        self._jobs: dict[str, IngestionJob] = {}

    async def submit(
        self,
        *,
        knowledge_base_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> IngestionJob:
        job_id = f"job-{uuid4().hex[:12]}"
        identity_bytes = _canonical_source_bytes(
            filename=filename,
            content_type=content_type,
            content=content,
        )
        source_hash = hashlib.sha256(identity_bytes).hexdigest()
        source_id = f"src-{source_hash[:16]}"
        job = IngestionJob(
            id=job_id,
            knowledge_base_id=knowledge_base_id,
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
            embeddings = await self._embedder.embed_documents(
                [chunk.text for chunk in chunks]
            )
            await self._writer.upsert_chunks(
                knowledge_base_id=knowledge_base_id,
                chunks=chunks,
                embeddings=embeddings,
            )
            job = job.model_copy(
                update={
                    "status": "completed",
                    "progress": 100,
                    "chunks_created": len(chunks),
                }
            )
        except Exception as exc:  # noqa: BLE001 - job boundary records adapter failures
            job = job.model_copy(
                update={
                    "status": "failed",
                    "progress": 100,
                    "error": str(exc),
                }
            )
        self._jobs[job_id] = job
        return job

    async def get_job(self, job_id: str) -> IngestionJob:
        return self._jobs[job_id]
