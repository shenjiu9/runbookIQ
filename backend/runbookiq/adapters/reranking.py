import json
from typing import Protocol

import httpx

from runbookiq.domain.retrieval import RankedChunk


class ChatClient(Protocol):
    async def chat(self, *, system: str, user: str, json_mode: bool = False) -> str: ...


class ChatReranker:
    """Model-backed reranker that hides provider prompting behind the reranker seam."""

    def __init__(self, client: ChatClient) -> None:
        self._client = client

    async def rerank(
        self,
        *,
        question: str,
        candidates: list[RankedChunk],
        limit: int,
    ) -> list[RankedChunk]:
        if not candidates:
            return []
        payload = {
            "question": question,
            "candidates": [
                {
                    "id": item.chunk.id,
                    "title": item.chunk.title,
                    "section": item.chunk.section_path,
                    "text": item.chunk.text[:1200],
                }
                for item in candidates
            ],
        }
        try:
            content = await self._client.chat(
                system=(
                    "Score each candidate's relevance to the incident question from 0 to 1. "
                    "Use semantic relevance, exact identifiers, and operational usefulness. "
                    'Return JSON only: {"scores":[{"id":"candidate-id","score":0.0}]}.'
                ),
                user=json.dumps(payload, ensure_ascii=False),
                json_mode=True,
            )
            raw_scores = json.loads(content)["scores"]
            scores = {
                str(item["id"]): min(1.0, max(0.0, float(item["score"])))
                for item in raw_scores
            }
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            scores = {}

        if not scores:
            return [
                item.model_copy(update={"rank": rank})
                for rank, item in enumerate(candidates[:limit], start=1)
            ]

        rescored = [
            item.model_copy(update={"score": round(scores.get(item.chunk.id, item.score), 6)})
            for item in candidates
        ]
        rescored.sort(key=lambda item: (-item.score, item.chunk.id))
        return [
            item.model_copy(update={"rank": rank})
            for rank, item in enumerate(rescored[:limit], start=1)
        ]
