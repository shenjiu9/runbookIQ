from typing import Protocol

from runbookiq.domain.retrieval import RankedChunk


class QueryRewriter(Protocol):
    async def rewrite(self, question: str) -> list[str]: ...


class Embedder(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...


class HybridIndex(Protocol):
    async def lexical_search(
        self,
        *,
        knowledge_base_id: str,
        queries: list[str],
        limit: int,
    ) -> list[RankedChunk]: ...

    async def vector_search(
        self,
        *,
        knowledge_base_id: str,
        embedding: list[float],
        limit: int,
    ) -> list[RankedChunk]: ...


class Reranker(Protocol):
    async def rerank(
        self,
        *,
        question: str,
        candidates: list[RankedChunk],
        limit: int,
    ) -> list[RankedChunk]: ...


class AnswerComposer(Protocol):
    async def compose(self, *, question: str, evidence: list[RankedChunk]) -> str: ...

