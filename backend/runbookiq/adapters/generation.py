import json
from typing import Protocol

import httpx

from runbookiq.domain.retrieval import RankedChunk


class ChatClient(Protocol):
    async def chat(self, *, system: str, user: str, json_mode: bool = False) -> str: ...


class ChatQueryRewriter:
    def __init__(self, client: ChatClient) -> None:
        self._client = client

    async def rewrite(self, question: str) -> list[str]:
        try:
            content = await self._client.chat(
                system=(
                    "Rewrite an SRE incident question into up to three concise search queries. "
                    "Preserve Kubernetes resource names, error strings, commands, and identifiers. "
                    'Return JSON only: {"queries":["..."]}.'
                ),
                user=question,
                json_mode=True,
            )
            queries = json.loads(content).get("queries", [])
            cleaned = [str(query).strip() for query in queries if str(query).strip()]
            return [question, *cleaned[:2]]
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
            return [question]


class ChatAnswerComposer:
    def __init__(self, client: ChatClient) -> None:
        self._client = client

    async def compose(self, *, question: str, evidence: list[RankedChunk]) -> str:
        if not evidence:
            return "当前知识库没有足够证据回答这个问题。"
        blocks = []
        for number, item in enumerate(evidence, start=1):
            context = item.chunk.parent_text or item.chunk.text
            blocks.append(
                f"[{number}] {item.chunk.title} > {item.chunk.section_path}\n{context}"
            )
        return await self._client.chat(
            system=(
                "You are a senior SRE incident assistant. Answer in Chinese. "
                "Use only the supplied evidence. Every operational claim must end with one or "
                "more citations such as [1] or [1][2]. Do not invent commands, causes, metrics, "
                "or configuration. If evidence is insufficient, say what is missing. "
                "Give a prioritized diagnostic sequence and preserve exact commands."
            ),
            user=f"Question:\n{question}\n\nEvidence:\n" + "\n\n".join(blocks),
        )
