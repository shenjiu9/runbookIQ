import hashlib
import time
from uuid import uuid4

from runbookiq.domain.models import (
    Answer,
    Citation,
    EvaluationReport,
    IngestionJob,
    RetrievalTrace,
    SourceDocument,
    TraceStage,
)


class DemoInvestigator:
    async def ask(self, *, knowledge_base_id: str, question: str) -> Answer:
        started = time.perf_counter()
        citation = Citation(
            number=1,
            source_id="k8s-pod-lifecycle",
            title="Kubernetes Docs: Pod lifecycle",
            section_path="Container states / CrashLoopBackOff",
            excerpt=(
                "A container in CrashLoopBackOff is repeatedly failing to start. "
                "Inspect container logs and configuration."
            ),
            source_url="https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/",
            scores={"bm25": 0.81, "vector": 0.89, "rerank": 0.92},
        )
        elapsed = max(1, int((time.perf_counter() - started) * 1000))
        return Answer(
            text=(
                "这通常意味着容器启动后持续退出。先执行 `kubectl logs --previous` "
                "检查上一轮容器日志，再核对最近发布的 ConfigMap、Secret、环境变量和探针配置。[1]"
            ),
            confidence=0.92,
            citations=[citation],
            trace=RetrievalTrace(
                query_id=f"demo-{hashlib.sha1(question.encode()).hexdigest()[:10]}",
                stages=[
                    TraceStage(name="query_rewrite", duration_ms=7, candidate_count=1),
                    TraceStage(name="hybrid_search", duration_ms=18, candidate_count=40),
                    TraceStage(name="rrf_fusion", duration_ms=3, candidate_count=20),
                    TraceStage(name="rerank", duration_ms=12, candidate_count=10),
                    TraceStage(
                        name="grounded_answer",
                        duration_ms=elapsed + 24,
                        candidate_count=1,
                    ),
                ],
            ),
        )


class InMemoryIngestion:
    def __init__(self) -> None:
        self._jobs: dict[str, IngestionJob] = {}

    async def submit(
        self,
        *,
        knowledge_base_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> IngestionJob:
        del content_type
        job_id = f"job-{uuid4().hex[:12]}"
        estimated_chunks = max(1, len(content.decode(errors="ignore").splitlines()) // 8)
        job = IngestionJob(
            id=job_id,
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            status="completed",
            progress=100,
            chunks_created=estimated_chunks,
        )
        self._jobs[job_id] = job
        return job

    async def get_job(self, job_id: str) -> IngestionJob:
        return self._jobs[job_id]

    async def replace(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> IngestionJob:
        del knowledge_base_id, filename, content_type, content
        raise KeyError(document_id)

    async def list_documents(self, knowledge_base_id: str) -> list[SourceDocument]:
        del knowledge_base_id
        return []

    async def cleanup_pending_objects(self) -> None:
        return None

    async def delete_document(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> None:
        del knowledge_base_id
        raise KeyError(document_id)

    async def get_document_content(
        self,
        *,
        knowledge_base_id: str,
        document_id: str,
    ) -> tuple[SourceDocument, bytes]:
        del knowledge_base_id
        raise FileNotFoundError(document_id)


class DemoEvaluator:
    def __init__(self) -> None:
        self._latest_by_knowledge_base: dict[str, EvaluationReport] = {}

    async def run(
        self,
        *,
        knowledge_base_id: str,
        cases: list[dict],
        suite_id: str,
        suite_total: int,
    ) -> EvaluationReport:
        report = EvaluationReport(
            run_id=f"eval-{uuid4().hex[:10]}",
            knowledge_base_id=knowledge_base_id,
            suite_id=suite_id,
            suite_total=suite_total,
            case_count=len(cases),
            evaluated_at="2026-01-01T00:00:00+00:00",
            duration_ms=1,
            judge="demo",
            metrics={
                "recall_at_5": 0.94,
                "mrr_at_5": 0.87,
                "precision_at_5": 0.96,
                "faithfulness": 0.92,
            },
        )
        self._latest_by_knowledge_base[knowledge_base_id] = report
        return report

    async def latest(self, knowledge_base_id: str) -> EvaluationReport | None:
        return self._latest_by_knowledge_base.get(knowledge_base_id)
