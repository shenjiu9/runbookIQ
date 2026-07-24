import json

import pytest

from runbookiq.adapters.reranking import ChatReranker
from runbookiq.domain.retrieval import DocumentChunk, RankedChunk


class ScoringChat:
    async def chat(self, *, system: str, user: str, json_mode: bool = False) -> str:
        assert "relevance" in system.lower()
        assert json_mode is True
        payload = json.loads(user)
        assert payload["question"] == "如何处理数据库连接池耗尽？"
        assert {item["id"] for item in payload["candidates"]} == {"runbook", "holiday"}
        return json.dumps(
            {
                "scores": [
                    {"id": "runbook", "score": 0.96},
                    {"id": "holiday", "score": 0.03},
                ]
            }
        )


class InvalidChat:
    async def chat(self, *, system: str, user: str, json_mode: bool = False) -> str:
        return "not-json"


def candidate(chunk_id: str, title: str, text: str, rank: int) -> RankedChunk:
    return RankedChunk(
        chunk=DocumentChunk(
            id=chunk_id,
            source_id=f"source-{chunk_id}",
            title=title,
            section_path=title,
            text=text,
            source_url=f"upload://{chunk_id}.md",
        ),
        rank=rank,
        score=0.5,
    )


@pytest.mark.asyncio
async def test_real_model_reranker_orders_evidence_by_relevance() -> None:
    reranker = ChatReranker(ScoringChat())
    candidates = [
        candidate("holiday", "休假制度", "年假需要提前三天申请。", 1),
        candidate("runbook", "数据库连接池手册", "检查活动连接和池等待队列。", 2),
    ]

    result = await reranker.rerank(
        question="如何处理数据库连接池耗尽？",
        candidates=candidates,
        limit=2,
    )

    assert [item.chunk.id for item in result] == ["runbook", "holiday"]
    assert [item.rank for item in result] == [1, 2]
    assert [item.score for item in result] == [0.96, 0.03]


@pytest.mark.asyncio
async def test_model_failure_preserves_the_fused_candidate_order() -> None:
    reranker = ChatReranker(InvalidChat())
    candidates = [
        candidate("z-first", "第一候选", "已经由 RRF 排在第一。", 1),
        candidate("a-second", "第二候选", "模型失败时不得越过第一候选。", 2),
    ]

    result = await reranker.rerank(
        question="模型失败时怎么办？",
        candidates=candidates,
        limit=2,
    )

    assert [item.chunk.id for item in result] == ["z-first", "a-second"]
    assert [item.rank for item in result] == [1, 2]
