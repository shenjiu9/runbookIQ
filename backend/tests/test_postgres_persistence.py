import os

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from runbookiq.adapters.knowledge_bases import PostgresKnowledgeBaseCatalog
from runbookiq.adapters.local import (
    ExtractiveAnswerComposer,
    HashingEmbedder,
    IdentityQueryRewriter,
    TokenOverlapReranker,
)
from runbookiq.adapters.postgres import PostgresKnowledgeIndex
from runbookiq.app import create_app
from runbookiq.evaluation.engine import EvaluationEngine, HeuristicFaithfulnessJudge
from runbookiq.ingestion.chunker import ParentChildChunker
from runbookiq.ingestion.manager import InlineIngestionManager
from runbookiq.ingestion.parser import DocumentParser
from runbookiq.investigation.engine import InvestigationEngine

DATABASE_URL = os.getenv(
    "RUNBOOKIQ_TEST_DATABASE_URL",
    "postgresql+asyncpg://runbookiq:runbookiq@127.0.0.1:55432/runbookiq",
)
pytestmark = pytest.mark.skipif(
    "RUNBOOKIQ_TEST_DATABASE_URL" not in os.environ,
    reason="set RUNBOOKIQ_TEST_DATABASE_URL to run the PostgreSQL integration test",
)


def persistent_app(engine: AsyncEngine):
    embedder = HashingEmbedder(dimensions=768)
    index = PostgresKnowledgeIndex(engine)
    investigator = InvestigationEngine(
        query_rewriter=IdentityQueryRewriter(),
        embedder=embedder,
        index=index,
        reranker=TokenOverlapReranker(),
        composer=ExtractiveAnswerComposer(),
    )
    return create_app(
        investigator=investigator,
        ingestion=InlineIngestionManager(
            parser=DocumentParser(),
            chunker=ParentChildChunker(),
            embedder=embedder,
            writer=index,
        ),
        evaluator=EvaluationEngine(
            investigator=investigator,
            faithfulness_judge=HeuristicFaithfulnessJudge(),
        ),
        knowledge_bases=PostgresKnowledgeBaseCatalog(engine),
    )


@pytest.mark.asyncio
async def test_knowledge_and_vectors_survive_application_restart() -> None:
    first_engine = create_async_engine(DATABASE_URL)
    first_app = persistent_app(first_engine)
    first_transport = httpx.ASGITransport(app=first_app)

    async with httpx.AsyncClient(transport=first_transport, base_url="http://test") as client:
        knowledge_base = (
            await client.post(
                "/api/knowledge-bases",
                json={"name": "持久化测试库", "description": "重启后仍可查询"},
            )
        ).json()
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": knowledge_base["id"]},
            files={
                "file": (
                    "durable.md",
                    "# 持久化证据\n\n代号 ORBIT-731 在重启后仍应可检索。",
                    "text/markdown",
                )
            },
        )
        assert uploaded.json()["status"] == "completed"
    await first_engine.dispose()

    second_engine = create_async_engine(DATABASE_URL)
    second_app = persistent_app(second_engine)
    second_transport = httpx.ASGITransport(app=second_app)
    async with httpx.AsyncClient(transport=second_transport, base_url="http://test") as client:
        listed = await client.get("/api/knowledge-bases")
        answered = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": knowledge_base["id"],
                "question": "ORBIT-731 是什么？",
            },
        )
        deleted = await client.delete(f"/api/knowledge-bases/{knowledge_base['id']}")

    await second_engine.dispose()
    assert knowledge_base["id"] in {item["id"] for item in listed.json()}
    assert "ORBIT-731" in answered.json()["answer"]
    assert answered.json()["citations"][0]["title"] == "持久化证据"
    assert deleted.status_code == 204
