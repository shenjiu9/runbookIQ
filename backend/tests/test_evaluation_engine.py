import httpx
import pytest

from runbookiq.app import create_app
from runbookiq.domain.models import Answer, Citation, RetrievalTrace
from runbookiq.evaluation.engine import EvaluationEngine, HeuristicFaithfulnessJudge


class TwoQuestionInvestigator:
    async def ask(self, *, knowledge_base_id: str, question: str) -> Answer:
        assert knowledge_base_id == "platform"
        expected = Citation(
            number=1 if question == "logs" else 2,
            source_id="expected-source",
            title="Expected",
            section_path="Expected",
            excerpt="Expected operational evidence.",
            source_url="runbook://expected",
        )
        distractor = Citation(
            number=2 if question == "logs" else 1,
            source_id="distractor",
            title="Distractor",
            section_path="Other",
            excerpt="Related but not sufficient.",
            source_url="runbook://distractor",
        )
        citations = [expected, distractor] if question == "logs" else [distractor, expected]
        return Answer(
            text="Grounded answer [1][2]",
            confidence=0.9,
            citations=citations,
            trace=RetrievalTrace(query_id=f"q-{question}", stages=[]),
        )


@pytest.mark.asyncio
async def test_evaluation_computes_retrieval_and_grounding_metrics_per_suite() -> None:
    evaluator = EvaluationEngine(
        investigator=TwoQuestionInvestigator(),
        faithfulness_judge=HeuristicFaithfulnessJudge(),
    )
    app = create_app(evaluator=evaluator)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/evaluations/run",
            json={
                "knowledge_base_id": "platform",
                "cases": [
                    {"question": "logs", "expected_source_ids": ["expected-source"]},
                    {"question": "config", "expected_source_ids": ["expected-source"]},
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["case_count"] == 2
    assert response.json()["metrics"] == {
        "recall_at_5": 1.0,
        "mrr_at_5": 0.75,
        "precision_at_5": 0.5,
        "faithfulness": 1.0,
    }
    assert len(response.json()["cases"]) == 2
    assert response.json()["cases"][1]["first_relevant_rank"] == 2

    latest = await evaluator.latest("platform")
    assert latest is not None
    assert latest.run_id == response.json()["run_id"]


@pytest.mark.asyncio
async def test_latest_evaluation_is_isolated_by_knowledge_base() -> None:
    evaluator = EvaluationEngine(
        investigator=TwoQuestionInvestigator(),
        faithfulness_judge=HeuristicFaithfulnessJudge(),
    )

    await evaluator.run(
        knowledge_base_id="platform",
        cases=[{"question": "logs", "expected_source_ids": ["expected-source"]}],
        suite_id="platform-operations-v1",
        suite_total=60,
    )

    assert await evaluator.latest("missing-retail-kb") is None
    assert (await evaluator.latest("platform")) is not None
