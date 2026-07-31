from typing import Protocol

from runbookiq.domain.models import Answer, EvaluationReport, IngestionJob, KnowledgeBase
from runbookiq.domain.tenancy import TenantContext, TenantSession


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

    async def latest(self, knowledge_base_id: str) -> EvaluationReport | None: ...


class TenantAccess(Protocol):
    authentication_required: bool

    async def register(
        self,
        *,
        email: str,
        password: str,
        organization_name: str,
        slug: str,
    ) -> TenantSession: ...

    async def authenticate(self, *, email: str, password: str) -> TenantSession: ...

    async def resolve(
        self,
        *,
        session_token: str | None,
        host: str,
    ) -> TenantContext | None: ...

    async def revoke_session(self, session_token: str | None) -> None: ...

    async def validate_csrf(
        self,
        session_token: str | None,
        csrf_token: str | None,
    ) -> bool: ...

    async def grant_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> None: ...

    async def revoke_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> None: ...

    async def can_access_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> bool: ...

    async def allowed_knowledge_base_ids(
        self,
        context: TenantContext,
    ) -> set[str] | None: ...

    async def domain_allowed(self, host: str) -> bool: ...
