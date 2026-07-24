import json
import re
import time
from datetime import UTC, datetime
from statistics import fmean
from typing import Protocol
from uuid import uuid4

import httpx

from runbookiq.domain.models import Answer, EvaluationCaseResult, EvaluationReport
from runbookiq.domain.ports import Investigator


class FaithfulnessJudge(Protocol):
    name: str

    async def score(self, *, question: str, answer: Answer) -> float: ...


class HeuristicFaithfulnessJudge:
    """Citation-validity fallback for offline development and deterministic CI."""

    name = "citation_validity_fallback"

    async def score(self, *, question: str, answer: Answer) -> float:
        del question
        markers = {int(value) for value in re.findall(r"\[(\d+)]", answer.text)}
        available = {citation.number for citation in answer.citations}
        if not markers or not available:
            return 0.0
        return 1.0 if markers <= available else len(markers & available) / len(markers)


class ChatClient(Protocol):
    async def chat(self, *, system: str, user: str, json_mode: bool = False) -> str: ...


class ChatFaithfulnessJudge:
    """LLM-as-judge adapter that checks whether claims are supported by evidence."""

    name = "llm_evidence_judge"

    def __init__(self, client: ChatClient) -> None:
        self._client = client
        self._fallback = HeuristicFaithfulnessJudge()

    async def score(self, *, question: str, answer: Answer) -> float:
        evidence = "\n\n".join(
            f"[{citation.number}] {citation.excerpt}" for citation in answer.citations
        )
        try:
            content = await self._client.chat(
                system=(
                    "You evaluate RAG faithfulness. Determine what fraction of factual and "
                    "operational claims in the answer are directly supported by the supplied "
                    "evidence. Ignore writing quality. Return JSON only: "
                    '{"score": 0.0, "reason": "short explanation"}. '
                    "The score must be between 0 and 1."
                ),
                user=(
                    f"Question:\n{question}\n\nAnswer:\n{answer.text}\n\n"
                    f"Evidence:\n{evidence}"
                ),
                json_mode=True,
            )
            score = float(json.loads(content)["score"])
            return round(min(1.0, max(0.0, score)), 4)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return await self._fallback.score(question=question, answer=answer)


class EvaluationEngine:
    def __init__(
        self,
        *,
        investigator: Investigator,
        faithfulness_judge: FaithfulnessJudge,
    ) -> None:
        self._investigator = investigator
        self._faithfulness_judge = faithfulness_judge
        self._latest: EvaluationReport | None = None

    async def run(
        self,
        *,
        knowledge_base_id: str,
        cases: list[dict],
        suite_id: str = "custom",
        suite_total: int | None = None,
    ) -> EvaluationReport:
        started = time.perf_counter()
        recalls: list[float] = []
        reciprocal_ranks: list[float] = []
        precisions: list[float] = []
        faithfulness_scores: list[float] = []
        case_results: list[EvaluationCaseResult] = []

        for case in cases:
            answer = await self._investigator.ask(
                knowledge_base_id=knowledge_base_id,
                question=case["question"],
            )
            expected = set(case["expected_source_ids"])
            retrieved = [citation.source_id for citation in answer.citations[:5]]
            retrieved_set = set(retrieved)
            recall = len(expected & retrieved_set) / len(expected)
            recalls.append(recall)

            first_relevant_rank = next(
                (rank for rank, source_id in enumerate(retrieved, start=1) if source_id in expected),
                None,
            )
            reciprocal_rank = 1 / first_relevant_rank if first_relevant_rank else 0.0
            reciprocal_ranks.append(reciprocal_rank)
            precision = (
                len(expected & retrieved_set) / len(retrieved_set) if retrieved_set else 0.0
            )
            precisions.append(precision)
            faithfulness = await self._faithfulness_judge.score(
                question=case["question"],
                answer=answer,
            )
            faithfulness_scores.append(faithfulness)
            case_results.append(
                EvaluationCaseResult(
                    question=case["question"],
                    expected_source_ids=sorted(expected),
                    retrieved_source_ids=retrieved,
                    first_relevant_rank=first_relevant_rank,
                    metrics={
                        "recall_at_5": round(recall, 4),
                        "reciprocal_rank_at_5": round(reciprocal_rank, 4),
                        "precision_at_5": round(precision, 4),
                        "faithfulness": round(faithfulness, 4),
                    },
                )
            )

        report = EvaluationReport(
            run_id=f"eval-{uuid4().hex[:12]}",
            suite_id=suite_id,
            suite_total=suite_total or len(cases),
            case_count=len(cases),
            evaluated_at=datetime.now(UTC).isoformat(),
            duration_ms=max(1, round((time.perf_counter() - started) * 1000)),
            judge=self._faithfulness_judge.name,
            metrics={
                "recall_at_5": round(fmean(recalls), 4),
                "mrr_at_5": round(fmean(reciprocal_ranks), 4),
                "precision_at_5": round(fmean(precisions), 4),
                "faithfulness": round(fmean(faithfulness_scores), 4),
            },
            metric_definitions={
                "recall_at_5": "黄金来源在前 5 条证据中的召回比例",
                "mrr_at_5": "首个黄金来源排名的平均倒数",
                "precision_at_5": "前 5 条唯一证据来源中黄金来源所占比例",
                "faithfulness": "答案中的事实和操作主张被引用证据直接支持的比例",
            },
            cases=case_results,
        )
        self._latest = report
        return report

    async def latest(self) -> EvaluationReport | None:
        return self._latest
