"""Exercise the local RAG pipeline with the configured DeepSeek chat model."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from runbookiq.runtime import app
from runbookiq.settings import Settings


async def main() -> None:
    settings = Settings()
    if not settings.chat_api_key.get_secret_value():
        raise RuntimeError("RUNBOOKIQ_CHAT_API_KEY is not configured")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://runbookiq.local",
        timeout=120,
    ) as client:
        runbook_path = PROJECT_ROOT / "examples" / "runbooks" / "crashloopbackoff.md"
        upload = await client.post(
            "/api/documents",
            data={"knowledge_base_id": "platform"},
            files={
                "file": (
                    runbook_path.name,
                    runbook_path.read_bytes(),
                    "text/markdown",
                )
            },
        )
        upload.raise_for_status()

        query = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "Pod 陷入 CrashLoopBackOff 时，如何检查上一次崩溃日志？",
            },
        )
        query.raise_for_status()
        payload = query.json()
        answer = payload["answer"]

    print(
        json.dumps(
            {
                "status": "ok",
                "chat_model": settings.chat_model,
                "answer_has_chinese": any("\u4e00" <= char <= "\u9fff" for char in answer),
                "answer_length": len(answer),
                "citation_count": len(payload["citations"]),
                "trace_stages": [stage["name"] for stage in payload["trace"]["stages"]],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
