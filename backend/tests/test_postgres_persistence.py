import os
from pathlib import Path

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
from runbookiq.adapters.object_storage import FileSystemDocumentStore
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


def persistent_app(engine: AsyncEngine, storage_path: Path):
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
            object_store=FileSystemDocumentStore(storage_path),
        ),
        evaluator=EvaluationEngine(
            investigator=investigator,
            faithfulness_judge=HeuristicFaithfulnessJudge(),
        ),
        knowledge_bases=PostgresKnowledgeBaseCatalog(engine),
    )


@pytest.mark.asyncio
async def test_knowledge_and_vectors_survive_application_restart(tmp_path: Path) -> None:
    first_engine = create_async_engine(DATABASE_URL)
    first_app = persistent_app(first_engine, tmp_path)
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
        document_id = uploaded.json()["document_id"]
    await first_engine.dispose()

    second_engine = create_async_engine(DATABASE_URL)
    second_app = persistent_app(second_engine, tmp_path)
    second_transport = httpx.ASGITransport(app=second_app)
    async with httpx.AsyncClient(transport=second_transport, base_url="http://test") as client:
        listed = await client.get("/api/knowledge-bases")
        documents = await client.get(
            f"/api/knowledge-bases/{knowledge_base['id']}/documents"
        )
        original = await client.get(
            f"/api/knowledge-bases/{knowledge_base['id']}/documents/{document_id}/content"
        )
        answered = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": knowledge_base["id"],
                "question": "ORBIT-731 是什么？",
            },
        )
        replaced = await client.put(
            f"/api/knowledge-bases/{knowledge_base['id']}/documents/{document_id}",
            files={
                "file": (
                    "durable.md",
                    "# 持久化证据\n\n代号 NOVA-902 已替换旧流程。",
                    "text/markdown",
                )
            },
        )
        after_replacement = await client.get(
            f"/api/knowledge-bases/{knowledge_base['id']}/documents"
        )
        old_answer = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": knowledge_base["id"],
                "question": "ORBIT-731",
            },
        )
        new_answer = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": knowledge_base["id"],
                "question": "NOVA-902",
            },
        )
        old_reuploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": knowledge_base["id"]},
            files={
                "file": (
                    "durable-old-copy.md",
                    "# 持久化证据\n\n代号 ORBIT-731 在重启后仍应可检索。",
                    "text/markdown",
                )
            },
        )
        after_old_reupload = await client.get(
            f"/api/knowledge-bases/{knowledge_base['id']}/documents"
        )
        deleted_document = await client.delete(
            f"/api/knowledge-bases/{knowledge_base['id']}/documents/{document_id}"
        )
        documents_after_delete = await client.get(
            f"/api/knowledge-bases/{knowledge_base['id']}/documents"
        )
        cascade_upload = await client.post(
            "/api/documents",
            data={"knowledge_base_id": knowledge_base["id"]},
            files={
                "file": (
                    "cascade.md",
                    "# 级联清理\n\nDELETE-WITH-KB-505",
                    "text/markdown",
                )
            },
        )
        deleted = await client.delete(f"/api/knowledge-bases/{knowledge_base['id']}")

    await second_engine.dispose()
    assert knowledge_base["id"] in {item["id"] for item in listed.json()}
    assert documents.json()[0]["id"] == document_id
    assert original.status_code == 200
    assert "ORBIT-731" in original.text
    assert "ORBIT-731" in answered.json()["answer"]
    assert answered.json()["citations"][0]["title"] == "持久化证据"
    assert replaced.json()["status"] == "completed"
    assert after_replacement.json()[0]["version"] == 2
    assert old_answer.json()["citations"] == []
    assert "NOVA-902" in new_answer.json()["answer"]
    assert old_reuploaded.json()["document_id"] == document_id
    assert len(after_old_reupload.json()) == 1
    assert after_old_reupload.json()[0]["version"] == 2
    assert deleted_document.status_code == 204
    assert documents_after_delete.json() == []
    assert cascade_upload.json()["status"] == "completed"
    assert deleted.status_code == 204
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []
