import httpx
import pytest

from runbookiq.app import create_app


@pytest.mark.asyncio
async def test_runtime_config_exposes_real_metadata_without_secrets() -> None:
    app = create_app(
        runtime_config={
            "mode": "production",
            "chat_provider": "openai_compatible",
            "chat_base_url": "https://api.example.com",
            "chat_model": "chat-model",
            "embedding_provider": "fastembed",
            "embedding_base_url": None,
            "embedding_model": "embedding-model",
            "embedding_dimensions": 768,
            "rerank_provider": "chat",
            "query_timeout_seconds": 60,
            "ocr_languages": "chi_sim+eng",
            "max_document_mib": 20,
        }
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/runtime-config")

    assert response.status_code == 200
    assert response.json()["chat_model"] == "chat-model"
    assert response.json()["embedding_dimensions"] == 768
    assert "api_key" not in response.text
