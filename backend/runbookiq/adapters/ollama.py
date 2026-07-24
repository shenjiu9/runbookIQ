import httpx


class OllamaClient:
    """Ollama chat and embedding adapter."""

    def __init__(
        self,
        *,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        timeout_seconds: float = 90,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._timeout = timeout_seconds

    async def embed_query(self, text: str) -> list[float]:
        embeddings = await self.embed_documents([text])
        return embeddings[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._embedding_model, "input": texts},
            )
            response.raise_for_status()
            return response.json()["embeddings"]

    async def chat(self, *, system: str, user: str, json_mode: bool = False) -> str:
        payload: dict = {
            "model": self._chat_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.1},
        }
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()["message"]["content"]
