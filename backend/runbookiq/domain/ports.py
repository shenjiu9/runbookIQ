from typing import Protocol

from runbookiq.domain.models import Answer, EvaluationReport, IngestionJob, KnowledgeBase


class KnowledgeBaseCatalog(Protocol):
    async def create(self, *, name: str, description: str) -> KnowledgeBase: ...

    async def list(self) -> list[KnowledgeBase]: ...

    async def get(self, knowledge_base_id: str) -> KnowledgeBase: ...

    async def delete(self, knowledge_base_id: str) -> None: ...


class Investigator(Protocol):
    async def ask(self, *, knowledge_base_id: str, question: str) -> Answer: ...


class IngestionManager(Protocol):
    async def submit(
        self,
        *,
        knowledge_base_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> IngestionJob: ...

    async def get_job(self, job_id: str) -> IngestionJob: ...


class Evaluator(Protocol):
    async def run(
        self,
        *,
        knowledge_base_id: str,
        cases: list[dict],
        suite_id: str,
        suite_total: int,
    ) -> EvaluationReport: ...

    async def latest(self) -> EvaluationReport | None: ...
