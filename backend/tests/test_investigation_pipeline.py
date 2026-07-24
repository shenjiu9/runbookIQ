import httpx
import pytest

from runbookiq.app import create_app
from runbookiq.domain.retrieval import DocumentChunk, RankedChunk
from runbookiq.investigation.engine import InvestigationEngine


class FixedRewriter:
    async def rewrite(self, question: str) -> list[str]:
        assert "CrashLoopBackOff" in question
        return [question, "pod restart configmap logs"]


class FixedEmbedder:
    async def embed_query(self, text: str) -> list[float]:
        assert text
        return [0.1, 0.2, 0.3]


class SplitRankIndex:
    def __init__(self) -> None:
        self.log_chunk = DocumentChunk(
            id="chunk-logs",
            source_id="k8s-debug-pods",
            title="Debug running pods",
            section_path="Container logs",
            text="Use kubectl logs --previous to inspect the last terminated container.",
            source_url="https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/",
        )
        self.config_chunk = DocumentChunk(
            id="chunk-config",
            source_id="runbook-config-rollout",
            title="Config rollout runbook",
            section_path="CrashLoopBackOff / Configuration",
            text="Compare mounted ConfigMap and Secret values with the previous deployment.",
            source_url="runbook://platform/config-rollout",
        )

    async def lexical_search(
        self, *, knowledge_base_id: str, queries: list[str], limit: int
    ) -> list[RankedChunk]:
        assert knowledge_base_id == "platform"
        assert limit == 20
        return [
            RankedChunk(chunk=self.log_chunk, rank=1, score=0.91),
            RankedChunk(chunk=self.config_chunk, rank=2, score=0.77),
        ]

    async def vector_search(
        self, *, knowledge_base_id: str, embedding: list[float], limit: int
    ) -> list[RankedChunk]:
        assert embedding == [0.1, 0.2, 0.3]
        return [
            RankedChunk(chunk=self.config_chunk, rank=1, score=0.94),
            RankedChunk(chunk=self.log_chunk, rank=2, score=0.83),
        ]


class PreferOperationalEvidence:
    async def rerank(
        self, *, question: str, candidates: list[RankedChunk], limit: int
    ) -> list[RankedChunk]:
        assert len(candidates) == 2
        by_id = {candidate.chunk.id: candidate for candidate in candidates}
        return [
            by_id["chunk-logs"].model_copy(update={"rank": 1, "score": 0.96}),
            by_id["chunk-config"].model_copy(update={"rank": 2, "score": 0.90}),
        ][:limit]


class GroundedComposer:
    async def compose(self, *, question: str, evidence: list[RankedChunk]) -> str:
        assert [item.chunk.id for item in evidence] == ["chunk-logs", "chunk-config"]
        return "先查看上一轮容器日志，再比较配置发布前后的 ConfigMap 和 Secret。[1][2]"


@pytest.mark.asyncio
async def test_query_pipeline_fuses_two_retrievers_reranks_and_numbers_citations() -> None:
    engine = InvestigationEngine(
        query_rewriter=FixedRewriter(),
        embedder=FixedEmbedder(),
        index=SplitRankIndex(),
        reranker=PreferOperationalEvidence(),
        composer=GroundedComposer(),
    )
    app = create_app(investigator=engine)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "Why is the pod in CrashLoopBackOff after a ConfigMap rollout?",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["answer"] == (
        "先查看上一轮容器日志，再比较配置发布前后的 ConfigMap 和 Secret。[1][2]"
    )
    assert [citation["number"] for citation in payload["citations"]] == [1, 2]
    assert [citation["source_id"] for citation in payload["citations"]] == [
        "k8s-debug-pods",
        "runbook-config-rollout",
    ]
    assert payload["citations"][0]["scores"] == {
        "bm25": 0.91,
        "vector": 0.83,
        "rrf": 0.032522,
        "rerank": 0.96,
    }
    assert [stage["name"] for stage in payload["trace"]["stages"]] == [
        "query_rewrite",
        "hybrid_search",
        "rrf_fusion",
        "rerank",
        "grounded_answer",
    ]
