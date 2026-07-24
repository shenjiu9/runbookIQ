import httpx
import pytest

from runbookiq.app import create_local_app


@pytest.mark.asyncio
async def test_user_can_create_list_and_delete_an_isolated_knowledge_base() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/knowledge-bases",
            json={"name": "人力资源制度", "description": "员工制度与报销规范"},
        )
        knowledge_base_id = created.json()["id"]
        listed = await client.get("/api/knowledge-bases")
        deleted = await client.delete(f"/api/knowledge-bases/{knowledge_base_id}")
        missing = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": knowledge_base_id,
                "question": "差旅住宿标准是多少？",
            },
        )

    assert created.status_code == 201
    assert created.json()["name"] == "人力资源制度"
    assert {item["id"] for item in listed.json()} >= {"platform", knowledge_base_id}
    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert missing.json()["detail"] == "知识库不存在"


@pytest.mark.asyncio
async def test_documents_and_answers_are_isolated_between_knowledge_bases() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        finance = (
            await client.post(
                "/api/knowledge-bases",
                json={"name": "财务制度", "description": "报销与预算"},
            )
        ).json()
        operations = (
            await client.post(
                "/api/knowledge-bases",
                json={"name": "运维手册", "description": "线上故障处理"},
            )
        ).json()

        finance_upload = await client.post(
            "/api/documents",
            data={"knowledge_base_id": finance["id"]},
            files={
                "file": (
                    "travel.md",
                    "# 差旅制度\n\n住宿上限是每晚 600 元。",
                    "text/markdown",
                )
            },
        )
        operations_upload = await client.post(
            "/api/documents",
            data={"knowledge_base_id": operations["id"]},
            files={
                "file": (
                    "restart.md",
                    "# Pod 重启\n\n先检查上一轮容器日志。",
                    "text/markdown",
                )
            },
        )
        finance_answer = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": finance["id"],
                "question": "住宿上限是多少？",
            },
        )
        operations_answer = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": operations["id"],
                "question": "住宿上限是多少？",
            },
        )

    assert finance_upload.json()["status"] == "completed"
    assert operations_upload.json()["status"] == "completed"
    assert "600" in finance_answer.json()["answer"]
    assert finance_answer.json()["citations"][0]["title"] == "差旅制度"
    assert operations_answer.json()["citations"] == []
    assert "没有足够证据" in operations_answer.json()["answer"]
