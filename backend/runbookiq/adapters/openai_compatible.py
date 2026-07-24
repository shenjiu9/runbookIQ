import httpx


class OpenAICompatibleChatClient:
    """Chat adapter for vendors exposing the OpenAI-compatible REST contract."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 90,
        thinking_enabled: bool | None = None,
        max_tokens: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._thinking_enabled = thinking_enabled
        self._max_tokens = max_tokens
        self._transport = transport

    async def chat(self, *, system: str, user: str, json_mode: bool = False) -> str:
        payload: dict = {
            "model": self._model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self._thinking_enabled is not None:
            payload["thinking"] = {
                "type": "enabled" if self._thinking_enabled else "disabled"
            }
        if self._max_tokens is not None:
            payload["max_tokens"] = self._max_tokens

        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]


class OpenAICompatibleEmbeddingClient:
    """Embedding adapter for vendors exposing the OpenAI-compatible REST contract."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        timeout_seconds: float = 90,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._timeout = timeout_seconds
        self._transport = transport

    async def embed_query(self, text: str) -> list[float]:
        embeddings = await self.embed_documents([text])
        return embeddings[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.post(
                f"{self._base_url}/embeddings",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "input": texts},
            )
            response.raise_for_status()

        rows = sorted(response.json()["data"], key=lambda item: item["index"])
        embeddings = [row["embedding"] for row in rows]
        if len(embeddings) != len(texts):
            raise ValueError("embedding provider returned an unexpected result count")
        if any(len(vector) != self._dimensions for vector in embeddings):
            raise ValueError(
                f"embedding provider must return {self._dimensions}-dimension vectors"
            )
        return embeddings
