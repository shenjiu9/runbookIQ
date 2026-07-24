import asyncio
from pathlib import Path
from typing import Protocol


class EmbeddingModel(Protocol):
    def embed(self, texts: list[str]): ...


class FastEmbedClient:
    """In-process ONNX embedding adapter with lazy model loading."""

    def __init__(
        self,
        *,
        model_name: str,
        dimensions: int,
        cache_dir: str | None = None,
        model: EmbeddingModel | None = None,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self._cache_dir = cache_dir
        self._model = model

    def _get_model(self) -> EmbeddingModel:
        if self._model is None:
            from fastembed import TextEmbedding

            cache_dir = (
                str(Path(self._cache_dir).expanduser().resolve())
                if self._cache_dir
                else None
            )
            self._model = TextEmbedding(
                model_name=self._model_name,
                cache_dir=cache_dir,
            )
        return self._model

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._embed([f"search_query: {text}"])
        return vectors[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed([f"search_document: {text}" for text in texts])

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        def generate() -> list[list[float]]:
            return [
                [float(value) for value in vector]
                for vector in self._get_model().embed(texts)
            ]

        vectors = await asyncio.to_thread(generate)
        if len(vectors) != len(texts):
            raise ValueError("embedding model returned an unexpected result count")
        if any(len(vector) != self._dimensions for vector in vectors):
            raise ValueError(
                f"embedding model must return {self._dimensions}-dimension vectors"
            )
        return vectors
