import asyncio

import httpx
import pytest

from runbookiq.adapters.local import HashingEmbedder, InMemoryKnowledgeIndex
from runbookiq.adapters.object_storage import InMemoryDocumentStore
from runbookiq.adapters.tenancy import InMemoryTenantAccess
from runbookiq.app import create_app, create_local_app
from runbookiq.ingestion.chunker import ParentChildChunker
from runbookiq.ingestion.manager import InlineIngestionManager
from runbookiq.ingestion.parser import DocumentParser


async def _upload(
    client: httpx.AsyncClient,
    *,
    filename: str,
    content: bytes,
    content_type: str = "text/markdown",
) -> httpx.Response:
    return await client.post(
        "/api/documents",
        data={"knowledge_base_id": "platform"},
        files={"file": (filename, content, content_type)},
    )


@pytest.mark.asyncio
async def test_uploaded_source_appears_in_the_knowledge_base_document_catalog() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await _upload(
            client,
            filename="checkout-runbook.md",
            content=b"# Checkout recovery\nRestart payment worker after queue drain.",
        )
        listed = await client.get("/api/knowledge-bases/platform/documents")

    assert uploaded.status_code == 202
    assert uploaded.json()["document_id"].startswith("doc-")
    assert listed.status_code == 200
    assert listed.json() == [
        {
            "id": uploaded.json()["document_id"],
            "knowledge_base_id": "platform",
            "source_id": "src-b6917240c6a7a9b6",
            "filename": "checkout-runbook.md",
            "content_type": "text/markdown",
            "size_bytes": 61,
            "checksum": "b6917240c6a7a9b600cff1889a6c66e72ef0410d777b54aa1da32af981318918",
            "version": 1,
            "status": "ready",
            "chunks_count": 1,
            "original_available": True,
            "created_at": listed.json()[0]["created_at"],
            "updated_at": listed.json()[0]["updated_at"],
        }
    ]


@pytest.mark.asyncio
async def test_replacing_a_document_atomically_switches_the_searchable_version() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await _upload(
            client,
            filename="refund-policy.md",
            content=b"# Refund policy\nLEGACY-451 refunds require a paper approval.",
        )
        document_id = uploaded.json()["document_id"]
        replaced = await client.put(
            f"/api/knowledge-bases/platform/documents/{document_id}",
            files={
                "file": (
                    "refund-policy.md",
                    b"# Refund policy\nCURRENT-982 refunds require digital approval.",
                    "text/markdown",
                )
            },
        )
        listed = await client.get("/api/knowledge-bases/platform/documents")
        old_answer = await client.post(
            "/api/query",
            json={"knowledge_base_id": "platform", "question": "LEGACY-451"},
        )
        current_answer = await client.post(
            "/api/query",
            json={"knowledge_base_id": "platform", "question": "CURRENT-982"},
        )

    assert replaced.status_code == 200
    assert replaced.json()["document_id"] == document_id
    assert len(listed.json()) == 1
    assert listed.json()[0]["version"] == 2
    assert listed.json()[0]["source_id"].startswith("src-")
    assert listed.json()[0]["source_id"] != document_id
    assert old_answer.json()["citations"] == []
    assert current_answer.json()["citations"][0]["source_id"] == listed.json()[0]["source_id"]
    assert "CURRENT-982" in current_answer.json()["answer"]


@pytest.mark.asyncio
async def test_concurrent_replacements_are_serialized_into_distinct_versions() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await _upload(
            client,
            filename="concurrent.md",
            content=b"# Policy\nBASE-100 is active.",
        )
        document_id = uploaded.json()["document_id"]
        first, second = await asyncio.gather(
            client.put(
                f"/api/knowledge-bases/platform/documents/{document_id}",
                files={"file": ("concurrent.md", b"# Policy\nFIRST-200", "text/markdown")},
            ),
            client.put(
                f"/api/knowledge-bases/platform/documents/{document_id}",
                files={"file": ("concurrent.md", b"# Policy\nSECOND-300", "text/markdown")},
            ),
        )
        listed = await client.get("/api/knowledge-bases/platform/documents")
        downloaded = await client.get(
            f"/api/knowledge-bases/platform/documents/{document_id}/content"
        )
        base_answer = await client.post(
            "/api/query",
            json={"knowledge_base_id": "platform", "question": "BASE-100"},
        )

    assert first.json()["status"] == "completed"
    assert second.json()["status"] == "completed"
    assert listed.json()[0]["version"] == 3
    assert downloaded.content in {b"# Policy\nFIRST-200", b"# Policy\nSECOND-300"}
    assert base_answer.json()["citations"] == []


@pytest.mark.asyncio
async def test_failed_replacement_preserves_the_current_document_and_original() -> None:
    original = b"# Escalation\nSAFE-731 is the active escalation rule."
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await _upload(
            client,
            filename="escalation.md",
            content=original,
        )
        document_id = uploaded.json()["document_id"]
        rejected = await client.put(
            f"/api/knowledge-bases/platform/documents/{document_id}",
            files={"file": ("escalation.pdf", b"not-a-pdf", "application/pdf")},
        )
        listed = await client.get("/api/knowledge-bases/platform/documents")
        downloaded = await client.get(
            f"/api/knowledge-bases/platform/documents/{document_id}/content"
        )
        answer = await client.post(
            "/api/query",
            json={"knowledge_base_id": "platform", "question": "SAFE-731"},
        )

    assert rejected.status_code == 422
    assert listed.json()[0]["version"] == 1
    assert downloaded.status_code == 200
    assert downloaded.content == original
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert "attachment" in downloaded.headers["content-disposition"]
    assert answer.json()["citations"][0]["source_id"] == listed.json()[0]["source_id"]


@pytest.mark.asyncio
async def test_deleting_one_document_removes_its_original_and_search_index() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await _upload(
            client,
            filename="obsolete.md",
            content=b"# Obsolete\nDELETE-884 must disappear with this source.",
        )
        document_id = uploaded.json()["document_id"]
        deleted = await client.delete(
            f"/api/knowledge-bases/platform/documents/{document_id}"
        )
        listed = await client.get("/api/knowledge-bases/platform/documents")
        downloaded = await client.get(
            f"/api/knowledge-bases/platform/documents/{document_id}/content"
        )
        answer = await client.post(
            "/api/query",
            json={"knowledge_base_id": "platform", "question": "DELETE-884"},
        )

    assert deleted.status_code == 204
    assert listed.json() == []
    assert downloaded.status_code == 404
    assert answer.json()["citations"] == []


@pytest.mark.asyncio
async def test_reuploading_identical_content_does_not_create_a_duplicate() -> None:
    class CountingEmbedder(HashingEmbedder):
        def __init__(self) -> None:
            super().__init__()
            self.document_calls = 0

        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            self.document_calls += 1
            await asyncio.sleep(0.01)
            return await super().embed_documents(texts)

    embedder = CountingEmbedder()
    index = InMemoryKnowledgeIndex()
    app = create_app(
        ingestion=InlineIngestionManager(
            parser=DocumentParser(),
            chunker=ParentChildChunker(),
            embedder=embedder,
            writer=index,
            object_store=InMemoryDocumentStore(),
        )
    )
    transport = httpx.ASGITransport(app=app)
    content = b"# Stable policy\nNo duplicate embedding should be created."

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first, second = await asyncio.gather(
            _upload(client, filename="policy.md", content=content),
            _upload(client, filename="policy-copy.md", content=content),
        )
        listed = await client.get("/api/knowledge-bases/platform/documents")

    assert first.json()["document_id"] == second.json()["document_id"]
    assert len(listed.json()) == 1
    assert listed.json()[0]["version"] == 1
    assert embedder.document_calls == 1


@pytest.mark.asyncio
async def test_reuploading_an_older_checksum_keeps_the_current_logical_document() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)
    original = b"# Returns\nOLD-171 requires paper approval."
    current = b"# Returns\nNEW-272 requires digital approval."

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await _upload(
            client,
            filename="returns.md",
            content=original,
        )
        document_id = uploaded.json()["document_id"]
        replaced = await client.put(
            f"/api/knowledge-bases/platform/documents/{document_id}",
            files={"file": ("returns.md", current, "text/markdown")},
        )
        old_reuploaded = await _upload(
            client,
            filename="returns-old-copy.md",
            content=original,
        )
        listed = await client.get("/api/knowledge-bases/platform/documents")
        downloaded = await client.get(
            f"/api/knowledge-bases/platform/documents/{document_id}/content"
        )

    assert replaced.json()["status"] == "completed"
    assert old_reuploaded.json()["status"] == "completed"
    assert old_reuploaded.json()["document_id"] == document_id
    assert len(listed.json()) == 1
    assert listed.json()[0]["version"] == 2
    assert downloaded.content == current


@pytest.mark.asyncio
async def test_background_ingestion_returns_a_job_before_embedding_finishes() -> None:
    class BlockingEmbedder(HashingEmbedder):
        def __init__(self) -> None:
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            self.started.set()
            await self.release.wait()
            return await super().embed_documents(texts)

    embedder = BlockingEmbedder()
    index = InMemoryKnowledgeIndex()
    app = create_app(
        ingestion=InlineIngestionManager(
            parser=DocumentParser(),
            chunker=ParentChildChunker(),
            embedder=embedder,
            writer=index,
            object_store=InMemoryDocumentStore(),
            run_in_background=True,
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await asyncio.wait_for(
            _upload(
                client,
                filename="large-chat.csv",
                content=(
                    b"conversation_id,timestamp,sender,message\n"
                    b"chat-1,2026-08-06 09:00,user,hello\n"
                ),
                content_type="text/csv",
            ),
            timeout=0.5,
        )
        assert uploaded.status_code == 202
        assert uploaded.json()["status"] in {"queued", "processing"}
        await asyncio.wait_for(embedder.started.wait(), timeout=0.5)

        embedder.release.set()
        for _ in range(20):
            observed = await client.get(
                f"/api/ingestion/jobs/{uploaded.json()['id']}"
            )
            if observed.json()["status"] == "completed":
                break
            await asyncio.sleep(0.01)

    assert observed.json()["status"] == "completed"
    assert observed.json()["chunks_created"] == 1


async def _register_owner(
    client: httpx.AsyncClient,
    *,
    email: str,
    organization_name: str,
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Strong-password-2026",
            "organization_name": organization_name,
        },
    )
    assert response.status_code == 201
    client.headers["X-CSRF-Token"] = client.cookies["runbookiq_csrf"]


@pytest.mark.asyncio
async def test_document_operations_cannot_cross_enterprise_boundaries() -> None:
    app = create_local_app(
        tenant_access=InMemoryTenantAccess(
            authentication_required=True,
            root_domain="knowledge.test",
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with (
        httpx.AsyncClient(transport=transport, base_url="https://knowledge.test") as alpha,
        httpx.AsyncClient(transport=transport, base_url="https://knowledge.test") as beta,
    ):
        await _register_owner(
            alpha,
            email="owner@alpha.example",
            organization_name="Alpha",
        )
        await _register_owner(
            beta,
            email="owner@beta.example",
            organization_name="Beta",
        )
        beta_knowledge_base_id = (await beta.get("/api/knowledge-bases")).json()[0]["id"]
        beta_upload = await beta.post(
            "/api/documents",
            data={"knowledge_base_id": beta_knowledge_base_id},
            files={"file": ("private.md", b"# Private\nBETA-ONLY", "text/markdown")},
        )
        document_id = beta_upload.json()["document_id"]

        cross_list = await alpha.get(
            f"/api/knowledge-bases/{beta_knowledge_base_id}/documents"
        )
        cross_replace = await alpha.put(
            f"/api/knowledge-bases/{beta_knowledge_base_id}/documents/{document_id}",
            files={"file": ("stolen.md", b"# Changed", "text/markdown")},
        )
        cross_delete = await alpha.delete(
            f"/api/knowledge-bases/{beta_knowledge_base_id}/documents/{document_id}"
        )

    assert cross_list.status_code == 404
    assert cross_replace.status_code == 404
    assert cross_delete.status_code == 404


@pytest.mark.asyncio
async def test_viewer_can_list_and_download_but_cannot_replace_or_delete_documents() -> None:
    app = create_local_app(
        tenant_access=InMemoryTenantAccess(
            authentication_required=True,
            root_domain="knowledge.test",
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://knowledge.test",
    ) as owner:
        await _register_owner(
            owner,
            email="owner@alpha.example",
            organization_name="Alpha",
        )
        knowledge_base_id = (await owner.get("/api/knowledge-bases")).json()[0]["id"]
        uploaded = await owner.post(
            "/api/documents",
            data={"knowledge_base_id": knowledge_base_id},
            files={"file": ("shared.md", b"# Shared\nReadable", "text/markdown")},
        )
        document_id = uploaded.json()["document_id"]
        invitation = (
            await owner.post(
                "/api/organization/invitations",
                json={"email": "viewer@alpha.example", "role": "viewer"},
            )
        ).json()

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://knowledge.test",
    ) as viewer:
        accepted = await viewer.post(
            "/api/auth/invitations/accept",
            json={
                "token": invitation["token"],
                "password": "Viewer-password-2026",
            },
        )
        assert accepted.status_code == 200
        viewer.headers["X-CSRF-Token"] = viewer.cookies["runbookiq_csrf"]
        listed = await viewer.get(
            f"/api/knowledge-bases/{knowledge_base_id}/documents"
        )
        downloaded = await viewer.get(
            f"/api/knowledge-bases/{knowledge_base_id}/documents/{document_id}/content"
        )
        replaced = await viewer.put(
            f"/api/knowledge-bases/{knowledge_base_id}/documents/{document_id}",
            files={"file": ("changed.md", b"# Changed", "text/markdown")},
        )
        deleted = await viewer.delete(
            f"/api/knowledge-bases/{knowledge_base_id}/documents/{document_id}"
        )

    assert listed.status_code == 200
    assert downloaded.status_code == 200
    assert replaced.status_code == 403
    assert deleted.status_code == 403
