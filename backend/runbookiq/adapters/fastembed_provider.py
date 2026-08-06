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
        batch_size: int = 32,
        cache_dir: str | None = None,
        model: EmbeddingModel | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self._model_name = model_name
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._cache_dir = cache_dir
        self._model = model
        self._embed_lock = asyncio.Lock()

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
        def generate(batch_texts: list[str]) -> list[list[float]]:
            return [
                [float(value) for value in vector]
                for vector in self._get_model().embed(batch_texts)
            ]

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            # FastEmbed keeps one ONNX session in process. Serializing each small
            # batch prevents concurrent uploads/queries from multiplying its peak
            # memory usage on small production hosts.
            async with self._embed_lock:
                vectors.extend(await asyncio.to_thread(generate, batch))
        if len(vectors) != len(texts):
            raise ValueError("embedding model returned an unexpected result count")
        if any(len(vector) != self._dimensions for vector in vectors):
            raise ValueError(
                f"embedding model must return {self._dimensions}-dimension vectors"
            )
        return vectors
