import asyncio
from dataclasses import dataclass

import httpx
import pytest

from runbookiq.app import create_app
from runbookiq.domain.models import Answer, Citation, RetrievalTrace, TraceStage


@dataclass
class FixedInvestigator:
    async def ask(self, *, knowledge_base_id: str, question: str) -> Answer:
        assert knowledge_base_id == "platform"
        assert question == "为什么 Pod 在配置发布后进入 CrashLoopBackOff？"
        return Answer(
            text="先检查容器日志和 ConfigMap 挂载内容。[1]",
            confidence=0.91,
            citations=[
                Citation(
                    number=1,
                    source_id="k8s-pod-lifecycle",
                    title="Kubernetes Pod lifecycle",
                    section_path="Debugging / CrashLoopBackOff",
                    excerpt="Use kubectl logs to inspect a repeatedly crashing container.",
                    source_url="https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/",
                    scores={"bm25": 0.81, "vector": 0.89, "rerank": 0.92},
                )
            ],
            trace=RetrievalTrace(
                query_id="query-001",
                stages=[
                    TraceStage(name="hybrid_search", duration_ms=24, candidate_count=40),
                    TraceStage(name="grounded_answer", duration_ms=31, candidate_count=1),
                ],
            ),
        )


@pytest.mark.asyncio
async def test_engineer_receives_grounded_answer_with_evidence_and_trace() -> None:
    app = create_app(investigator=FixedInvestigator())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "为什么 Pod 在配置发布后进入 CrashLoopBackOff？",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "先检查容器日志和 ConfigMap 挂载内容。[1]",
        "confidence": 0.91,
        "citations": [
            {
                "number": 1,
                "source_id": "k8s-pod-lifecycle",
                "title": "Kubernetes Pod lifecycle",
                "section_path": "Debugging / CrashLoopBackOff",
                "excerpt": "Use kubectl logs to inspect a repeatedly crashing container.",
                "source_url": "https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/",
                "scores": {"bm25": 0.81, "vector": 0.89, "rerank": 0.92},
            }
        ],
        "trace": {
            "query_id": "query-001",
            "stages": [
                {"name": "hybrid_search", "duration_ms": 24, "candidate_count": 40},
                {"name": "grounded_answer", "duration_ms": 31, "candidate_count": 1},
            ],
        },
    }


@pytest.mark.asyncio
async def test_empty_question_is_rejected_before_retrieval() -> None:
    app = create_app(investigator=FixedInvestigator())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/query",
            json={"knowledge_base_id": "platform", "question": "   "},
        )

    assert response.status_code == 422


@dataclass
class NeverFinishingInvestigator:
    async def ask(self, *, knowledge_base_id: str, question: str) -> Answer:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_query_returns_gateway_timeout_when_model_never_finishes() -> None:
    app = create_app(
        investigator=NeverFinishingInvestigator(),
        query_timeout_seconds=0.01,
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/query",
            json={
                "knowledge_base_id": "platform",
                "question": "Why is the Deployment still restarting?",
            },
        )

    assert response.status_code == 504
    assert response.json()["detail"] == "模型响应超时，请稍后重试。"
