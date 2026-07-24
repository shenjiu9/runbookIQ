import asyncio
import time
from uuid import uuid4

from runbookiq.domain.models import (
    Answer,
    Citation,
    RetrievalTrace,
    TraceStage,
)
from runbookiq.domain.retrieval import RankedChunk
from runbookiq.investigation.fusion import reciprocal_rank_fusion
from runbookiq.investigation.ports import (
    AnswerComposer,
    Embedder,
    HybridIndex,
    QueryRewriter,
    Reranker,
)


def _elapsed_ms(started: float) -> int:
    return max(1, round((time.perf_counter() - started) * 1000))


class InvestigationEngine:
    """Deep module for observable hybrid retrieval and grounded answering."""

    def __init__(
        self,
        *,
        query_rewriter: QueryRewriter,
        embedder: Embedder,
        index: HybridIndex,
        reranker: Reranker,
        composer: AnswerComposer,
        lexical_limit: int = 20,
        vector_limit: int = 20,
        rerank_limit: int = 8,
        evidence_limit: int = 5,
    ) -> None:
        self._query_rewriter = query_rewriter
        self._embedder = embedder
        self._index = index
        self._reranker = reranker
        self._composer = composer
        self._lexical_limit = lexical_limit
        self._vector_limit = vector_limit
        self._rerank_limit = rerank_limit
        self._evidence_limit = evidence_limit

    async def ask(self, *, knowledge_base_id: str, question: str) -> Answer:
        stages: list[TraceStage] = []

        started = time.perf_counter()
        rewritten_queries, embedding = await asyncio.gather(
            self._query_rewriter.rewrite(question),
            self._embedder.embed_query(question),
        )
        stages.append(
            TraceStage(
                name="query_rewrite",
                duration_ms=_elapsed_ms(started),
                candidate_count=len(rewritten_queries),
            )
        )

        started = time.perf_counter()
        lexical, vector = await asyncio.gather(
            self._index.lexical_search(
                knowledge_base_id=knowledge_base_id,
                queries=rewritten_queries,
                limit=self._lexical_limit,
            ),
            self._index.vector_search(
                knowledge_base_id=knowledge_base_id,
                embedding=embedding,
                limit=self._vector_limit,
            ),
        )
        stages.append(
            TraceStage(
                name="hybrid_search",
                duration_ms=_elapsed_ms(started),
                candidate_count=len(lexical) + len(vector),
            )
        )

        started = time.perf_counter()
        fused = reciprocal_rank_fusion(lexical, vector)
        stages.append(
            TraceStage(
                name="rrf_fusion",
                duration_ms=_elapsed_ms(started),
                candidate_count=len(fused),
            )
        )

        started = time.perf_counter()
        reranked = await self._reranker.rerank(
            question=question,
            candidates=fused,
            limit=self._rerank_limit,
        )
        for item in reranked:
            item.component_scores["rerank"] = round(item.score, 6)
        evidence = reranked[: self._evidence_limit]
        stages.append(
            TraceStage(
                name="rerank",
                duration_ms=_elapsed_ms(started),
                candidate_count=len(reranked),
            )
        )

        started = time.perf_counter()
        text = await self._composer.compose(question=question, evidence=evidence)
        stages.append(
            TraceStage(
                name="grounded_answer",
                duration_ms=_elapsed_ms(started),
                candidate_count=len(evidence),
            )
        )

        citations = [
            self._to_citation(number=number, item=item)
            for number, item in enumerate(evidence, start=1)
        ]
        confidence = round(evidence[0].score if evidence else 0.0, 4)
        return Answer(
            text=text,
            confidence=confidence,
            citations=citations,
            trace=RetrievalTrace(
                query_id=f"q-{uuid4().hex[:16]}",
                stages=stages,
            ),
        )

    @staticmethod
    def _to_citation(*, number: int, item: RankedChunk) -> Citation:
        excerpt = item.chunk.text
        if len(excerpt) > 600:
            excerpt = f"{excerpt[:597]}..."
        scores = {
            key: value
            for key, value in item.component_scores.items()
            if key in {"bm25", "vector", "rrf", "rerank"}
        }
        return Citation(
            number=number,
            source_id=item.chunk.source_id,
            title=item.chunk.title,
            section_path=item.chunk.section_path,
            excerpt=excerpt,
            source_url=item.chunk.source_url,
            scores=scores,
        )
