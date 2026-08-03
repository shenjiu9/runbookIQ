import hashlib
import math
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from runbookiq.domain.models import SourceDocument
from runbookiq.domain.retrieval import DocumentChunk, RankedChunk


def _terms(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_./:-]*|[\u4e00-\u9fff]+", text.lower())


class HashingEmbedder:
    """Small deterministic embedding adapter for tests and zero-config demo mode."""

    def __init__(self, dimensions: int = 256) -> None:
        self._dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for term in _terms(text):
            digest = hashlib.blake2b(term.encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest, "big") % self._dimensions
            vector[bucket] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]


class InMemoryKnowledgeIndex:
    def __init__(self) -> None:
        self._chunks: dict[str, dict[str, DocumentChunk]] = defaultdict(dict)
        self._embeddings: dict[str, dict[str, list[float]]] = defaultdict(dict)
        self._documents: dict[str, dict[str, SourceDocument]] = defaultdict(dict)
        self._checksum_documents: dict[str, dict[str, str]] = defaultdict(dict)
        self._document_chunks: dict[str, dict[str, set[str]]] = defaultdict(dict)
        self._pending_object_deletions: dict[str, datetime] = {}

    async def stage_object(self, storage_key: str) -> None:
        self._pending_object_deletions[storage_key] = datetime.now(UTC) + timedelta(
            hours=1
        )

    async def upsert_chunks(
        self,
        *,
        knowledge_base_id: str,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> None:
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            self._chunks[knowledge_base_id][chunk.id] = chunk
            self._embeddings[knowledge_base_id][chunk.id] = embedding

    async def replace_document(
        self,
        *,
        document: SourceDocument,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> str | None:
        knowledge_base_id = document.knowledge_base_id
        current = self._documents[knowledge_base_id].get(document.id)
        if current is None and document.version != 1:
            raise RuntimeError("document version changed; retry replacement")
        if current is not None and document.version != current.version + 1:
            raise RuntimeError("document version changed; retry replacement")
        mapped_document_id = self._checksum_documents[knowledge_base_id].get(
            document.checksum
        )
        if mapped_document_id not in {None, document.id}:
            raise RuntimeError("document checksum is already assigned")
        for chunk_id in self._document_chunks[knowledge_base_id].get(document.id, set()):
            self._chunks[knowledge_base_id].pop(chunk_id, None)
            self._embeddings[knowledge_base_id].pop(chunk_id, None)
        await self.upsert_chunks(
            knowledge_base_id=knowledge_base_id,
            chunks=chunks,
            embeddings=embeddings,
        )
        self._documents[knowledge_base_id][document.id] = document.model_copy(deep=True)
        self._checksum_documents[knowledge_base_id][document.checksum] = document.id
        self._document_chunks[knowledge_base_id][document.id] = {
            chunk.id for chunk in chunks
        }
        if document.storage_key:
            self._pending_object_deletions.pop(document.storage_key, None)
        if current and current.storage_key and current.storage_key != document.storage_key:
            self._pending_object_deletions[current.storage_key] = datetime.now(UTC)
        return current.storage_key if current else None

    async def get_document(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> SourceDocument:
        try:
            return self._documents[knowledge_base_id][document_id].model_copy(deep=True)
        except KeyError as exc:
            raise KeyError(document_id) from exc

    async def find_document_by_checksum(
        self,
        *,
        knowledge_base_id: str,
        checksum: str,
    ) -> SourceDocument | None:
        document_id = self._checksum_documents[knowledge_base_id].get(checksum)
        if document_id is None:
            return None
        document = self._documents[knowledge_base_id].get(document_id)
        return document.model_copy(deep=True) if document else None

    async def list_documents(self, knowledge_base_id: str) -> list[SourceDocument]:
        return sorted(
            (
                document.model_copy(deep=True)
                for document in self._documents[knowledge_base_id].values()
            ),
            key=lambda document: (document.updated_at, document.id),
            reverse=True,
        )

    async def delete_document(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> SourceDocument:
        try:
            document = self._documents[knowledge_base_id].pop(document_id)
        except KeyError as exc:
            raise KeyError(document_id) from exc
        for chunk_id in self._document_chunks[knowledge_base_id].pop(document_id, set()):
            self._chunks[knowledge_base_id].pop(chunk_id, None)
            self._embeddings[knowledge_base_id].pop(chunk_id, None)
        self._checksum_documents[knowledge_base_id] = {
            checksum: mapped_document_id
            for checksum, mapped_document_id in self._checksum_documents[
                knowledge_base_id
            ].items()
            if mapped_document_id != document_id
        }
        if document.storage_key:
            self._pending_object_deletions[document.storage_key] = datetime.now(UTC)
        return document

    async def list_pending_object_deletions(self) -> list[str]:
        now = datetime.now(UTC)
        return sorted(
            storage_key
            for storage_key, delete_after in self._pending_object_deletions.items()
            if delete_after <= now
        )

    async def confirm_object_deletion(self, storage_key: str) -> None:
        self._pending_object_deletions.pop(storage_key, None)

    async def lexical_search(
        self,
        *,
        knowledge_base_id: str,
        queries: list[str],
        limit: int,
    ) -> list[RankedChunk]:
        query_terms = set(_terms(" ".join(queries)))
        scored: list[tuple[float, DocumentChunk]] = []
        for chunk in self._chunks[knowledge_base_id].values():
            haystack = _terms(
                f"{chunk.title} {chunk.section_path} {chunk.text} {chunk.parent_text or ''}"
            )
            overlap = sum(1 for term in haystack if term in query_terms)
            if overlap:
                score = overlap / math.sqrt(max(1, len(haystack)))
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [
            RankedChunk(chunk=chunk, rank=rank, score=round(score, 6))
            for rank, (score, chunk) in enumerate(scored[:limit], start=1)
        ]

    async def vector_search(
        self,
        *,
        knowledge_base_id: str,
        embedding: list[float],
        limit: int,
    ) -> list[RankedChunk]:
        scored: list[tuple[float, DocumentChunk]] = []
        for chunk_id, chunk_embedding in self._embeddings[knowledge_base_id].items():
            score = sum(a * b for a, b in zip(embedding, chunk_embedding, strict=True))
            if score > 0:
                scored.append((score, self._chunks[knowledge_base_id][chunk_id]))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [
            RankedChunk(chunk=chunk, rank=rank, score=round(score, 6))
            for rank, (score, chunk) in enumerate(scored[:limit], start=1)
        ]


class IdentityQueryRewriter:
    async def rewrite(self, question: str) -> list[str]:
        return [question]


class TokenOverlapReranker:
    async def rerank(
        self,
        *,
        question: str,
        candidates: list[RankedChunk],
        limit: int,
    ) -> list[RankedChunk]:
        question_terms = set(_terms(question))
        rescored: list[RankedChunk] = []
        for candidate in candidates:
            document_terms = set(
                _terms(
                    f"{candidate.chunk.title} {candidate.chunk.section_path} "
                    f"{candidate.chunk.text}"
                )
            )
            overlap = len(question_terms & document_terms) / max(1, len(question_terms))
            score = min(0.99, 0.55 + overlap * 0.4 + candidate.score)
            rescored.append(candidate.model_copy(update={"score": round(score, 6)}))
        rescored.sort(key=lambda item: (-item.score, item.chunk.id))
        return [
            item.model_copy(update={"rank": rank})
            for rank, item in enumerate(rescored[:limit], start=1)
        ]


class ExtractiveAnswerComposer:
    """Deterministic local composer; production uses the grounded Ollama adapter."""

    async def compose(self, *, question: str, evidence: list[RankedChunk]) -> str:
        del question
        if not evidence:
            return "当前知识库中没有足够证据回答这个问题。"
        first = evidence[0].chunk.parent_text or evidence[0].chunk.text
        normalized = " ".join(first.split())
        if len(normalized) > 240:
            normalized = f"{normalized[:237]}..."
        return f"根据检索到的运行手册证据，建议优先参考以下内容：{normalized} [1]"
