from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from runbookiq.app import create_app, create_local_app
from runbookiq.domain.models import EvaluationReport


@dataclass
class FixedEvaluator:
    report: EvaluationReport | None = None

    async def run(
        self,
        *,
        knowledge_base_id: str,
        cases: list[dict],
        suite_id: str,
        suite_total: int,
    ) -> EvaluationReport:
        assert knowledge_base_id == "platform"
        assert suite_id == "custom"
        assert suite_total == 1
        assert cases == [
            {
                "question": "How do I inspect a crashing pod?",
                "expected_source_ids": ["k8s-pod-lifecycle"],
            }
        ]
        self.report = EvaluationReport(
            run_id="eval-001",
            knowledge_base_id=knowledge_base_id,
            suite_id=suite_id,
            suite_total=suite_total,
            case_count=1,
            evaluated_at="2026-07-24T00:00:00+00:00",
            duration_ms=25,
            judge="fixed",
            metrics={
                "recall_at_5": 1.0,
                "mrr_at_5": 1.0,
                "precision_at_5": 1.0,
                "faithfulness": 0.94,
            },
        )
        return self.report

    async def latest(self, knowledge_base_id: str) -> EvaluationReport | None:
        if self.report and self.report.knowledge_base_id == knowledge_base_id:
            return self.report
        return None


@pytest.mark.asyncio
async def test_evaluation_run_returns_resume_worthy_retrieval_metrics() -> None:
    evaluator = FixedEvaluator()
    app = create_app(evaluator=evaluator)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/evaluations/run",
            json={
                "knowledge_base_id": "platform",
                "cases": [
                    {
                        "question": "How do I inspect a crashing pod?",
                        "expected_source_ids": ["k8s-pod-lifecycle"],
                    }
                ],
            },
        )
        latest = await client.get(
            "/api/evaluations/latest",
            params={"knowledge_base_id": "platform"},
        )

    assert response.status_code == 200
    assert response.json()["run_id"] == "eval-001"
    assert response.json()["metrics"] == {
        "recall_at_5": 1.0,
        "mrr_at_5": 1.0,
        "precision_at_5": 1.0,
        "faithfulness": 0.94,
    }

    assert latest.status_code == 200
    assert latest.json()["run_id"] == "eval-001"


@pytest.mark.asyncio
async def test_evaluation_suites_are_scoped_to_their_knowledge_base() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        platform_suites = await client.get(
            "/api/knowledge-bases/platform/evaluation-suites"
        )
        created = await client.post(
            "/api/knowledge-bases",
            json={"name": "星港零售门店运营", "description": "零售知识库"},
        )
        retail_id = created.json()["id"]
        retail_suites = await client.get(
            f"/api/knowledge-bases/{retail_id}/evaluation-suites"
        )

    assert platform_suites.status_code == 200
    assert platform_suites.json() == [
        {
            "id": "platform-operations-v1",
            "knowledge_base_id": "platform",
            "name": "平台故障调查基准 v1",
            "description": "Kubernetes、配置发布与探针事故的中英文黄金问题",
            "case_count": 60,
        },
    ]
    assert retail_suites.status_code == 200
    assert retail_suites.json() == []


@pytest.mark.asyncio
async def test_chat_suite_attaches_only_after_its_transcript_is_uploaded() -> None:
    app = create_local_app()
    transport = httpx.ASGITransport(app=app)
    project_root = Path(__file__).resolve().parents[2]
    transcript = (
        project_root / "examples" / "chat" / "customer-support-synthetic.json"
    ).read_bytes()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/knowledge-bases",
            json={"name": "客服聊天测试", "description": "模拟聊天记录"},
        )
        knowledge_base_id = created.json()["id"]
        before = await client.get(
            f"/api/knowledge-bases/{knowledge_base_id}/evaluation-suites"
        )
        uploaded = await client.post(
            "/api/documents",
            data={"knowledge_base_id": knowledge_base_id},
            files={
                "file": (
                    "customer-support-synthetic.json",
                    transcript,
                    "application/json",
                )
            },
        )
        after = await client.get(
            f"/api/knowledge-bases/{knowledge_base_id}/evaluation-suites"
        )
        evaluated = await client.post(
            "/api/evaluations/run",
            json={
                "knowledge_base_id": knowledge_base_id,
                "suite_id": "chat-support-v1",
                "max_cases": 1,
            },
        )

    assert before.json() == []
    assert uploaded.json()["status"] == "completed"
    assert after.json() == [
        {
            "id": "chat-support-v1",
            "knowledge_base_id": knowledge_base_id,
            "name": "中文客服聊天记录基准 v1",
            "description": "12 个模拟客服会话的精确编号与自然语言检索黄金问题",
            "case_count": 24,
        }
    ]
    assert evaluated.status_code == 200
    assert evaluated.json()["knowledge_base_id"] == knowledge_base_id


@pytest.mark.asyncio
async def test_platform_suite_cannot_run_against_a_retail_knowledge_base() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/knowledge-bases",
            json={"name": "星港零售门店运营", "description": "零售知识库"},
        )
        response = await client.post(
            "/api/evaluations/run",
            json={
                "knowledge_base_id": created.json()["id"],
                "suite_id": "platform-operations-v1",
                "max_cases": 6,
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "该评测集不属于当前知识库，已禁止运行"
