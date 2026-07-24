import pytest

from runbookiq.adapters.fastembed_provider import FastEmbedClient


class FixedEmbeddingModel:
    def __init__(self) -> None:
        self.inputs: list[list[str]] = []

    def embed(self, texts: list[str]):
        self.inputs.append(texts)
        return iter(
            [
                [1.0, 0.0, 0.0]
                for _ in texts
            ]
        )


@pytest.mark.asyncio
async def test_fastembed_uses_retrieval_prefixes_and_returns_real_vectors() -> None:
    model = FixedEmbeddingModel()
    client = FastEmbedClient(
        model_name="nomic-ai/nomic-embed-text-v1.5-Q",
        dimensions=3,
        model=model,
    )

    query = await client.embed_query("数据库连接池耗尽")
    documents = await client.embed_documents(["检查活动连接", "查看等待队列"])

    assert query == [1.0, 0.0, 0.0]
    assert documents == [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    assert model.inputs == [
        ["search_query: 数据库连接池耗尽"],
        ["search_document: 检查活动连接", "search_document: 查看等待队列"],
    ]
