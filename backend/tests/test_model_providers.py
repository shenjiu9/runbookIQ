import json

import httpx
import pytest

from runbookiq.adapters.openai_compatible import (
    OpenAICompatibleChatClient,
    OpenAICompatibleEmbeddingClient,
)


@pytest.mark.asyncio
async def test_openai_compatible_chat_uses_vendor_endpoint_and_api_key():
    observed: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers["authorization"]
        observed["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "grounded answer [1]"}}]},
        )

    client = OpenAICompatibleChatClient(
        base_url="https://vendor.example/v1",
        api_key="vendor-secret",
        model="vendor-chat-model",
        transport=httpx.MockTransport(handler),
    )

    result = await client.chat(
        system="Use supplied evidence only.",
        user="Why did the pod restart?",
        json_mode=True,
    )

    assert result == "grounded answer [1]"
    assert observed == {
        "url": "https://vendor.example/v1/chat/completions",
        "authorization": "Bearer vendor-secret",
        "payload": {
            "model": "vendor-chat-model",
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": "Use supplied evidence only."},
                {"role": "user", "content": "Why did the pod restart?"},
            ],
            "response_format": {"type": "json_object"},
        },
    }


@pytest.mark.asyncio
async def test_chat_client_can_disable_deepseek_thinking_and_limit_output():
    observed: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "grounded answer"}}]},
        )

    client = OpenAICompatibleChatClient(
        base_url="https://api.deepseek.com",
        api_key="secret",
        model="deepseek-v4-flash",
        thinking_enabled=False,
        max_tokens=1600,
        transport=httpx.MockTransport(handler),
    )

    await client.chat(system="Use evidence only.", user="Diagnose the incident.")

    assert observed["payload"]["thinking"] == {"type": "disabled"}
    assert observed["payload"]["max_tokens"] == 1600


@pytest.mark.asyncio
async def test_openai_compatible_embeddings_preserve_vendor_result_order():
    observed: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers["authorization"]
        observed["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0, 0.0]},
                    {"index": 0, "embedding": [1.0, 0.0, 0.0]},
                ]
            },
        )

    client = OpenAICompatibleEmbeddingClient(
        base_url="https://embedding-vendor.example/v1",
        api_key="embedding-secret",
        model="embedding-model",
        dimensions=3,
        transport=httpx.MockTransport(handler),
    )

    result = await client.embed_documents(["first document", "second document"])

    assert result == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert observed == {
        "url": "https://embedding-vendor.example/v1/embeddings",
        "authorization": "Bearer embedding-secret",
        "payload": {
            "model": "embedding-model",
            "input": ["first document", "second document"],
        },
    }
