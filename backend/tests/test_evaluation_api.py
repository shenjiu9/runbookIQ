from dataclasses import dataclass

import httpx
import pytest

from runbookiq.app import create_app
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

    async def latest(self) -> EvaluationReport | None:
        return self.report


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
        latest = await client.get("/api/evaluations/latest")

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
