from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from runbookiq.adapters.demo import DemoEvaluator, DemoInvestigator, InMemoryIngestion
from runbookiq.adapters.knowledge_bases import InMemoryKnowledgeBaseCatalog
from runbookiq.adapters.local import (
    ExtractiveAnswerComposer,
    HashingEmbedder,
    IdentityQueryRewriter,
    InMemoryKnowledgeIndex,
    TokenOverlapReranker,
)
from runbookiq.adapters.tenancy import OpenTenantAccess
from runbookiq.api.routes import router
from runbookiq.domain.ports import (
    Evaluator,
    IngestionManager,
    Investigator,
    KnowledgeBaseCatalog,
    TenantAccess,
)
from runbookiq.evaluation.engine import (
    EvaluationEngine,
    FaithfulnessJudge,
    HeuristicFaithfulnessJudge,
)
from runbookiq.ingestion.chunker import ParentChildChunker
from runbookiq.ingestion.manager import InlineIngestionManager
from runbookiq.ingestion.parser import DocumentParser
from runbookiq.investigation.engine import InvestigationEngine
from runbookiq.investigation.ports import AnswerComposer, QueryRewriter
from runbookiq.security import (
    AbuseGuard,
    DisabledTurnstileVerifier,
    InMemoryAbuseGuard,
    TurnstileVerifier,
    UsageLimits,
)


def create_app(
    *,
    investigator: Investigator | None = None,
    ingestion: IngestionManager | None = None,
    evaluator: Evaluator | None = None,
    knowledge_bases: KnowledgeBaseCatalog | None = None,
    tenant_access: TenantAccess | None = None,
    query_timeout_seconds: float = 60,
    runtime_config: dict[str, str | int | float | None] | None = None,
    secure_cookies: bool = False,
    production_mode: bool = False,
    allowed_hosts: list[str] | None = None,
    abuse_guard: AbuseGuard | None = None,
    usage_limits: UsageLimits | None = None,
    turnstile_verifier: TurnstileVerifier | None = None,
    turnstile_site_key: str = "",
    trust_proxy_headers: bool = False,
) -> FastAPI:
    app = FastAPI(
        title="RunbookIQ",
        version="0.1.0",
        description="Incident investigation RAG workbench",
        docs_url=None if production_mode else "/docs",
        redoc_url=None if production_mode else "/redoc",
        openapi_url=None if production_mode else "/openapi.json",
    )
    if allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=allowed_hosts,
        )
    development_origins = {
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:4173",
    }
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[] if production_mode else sorted(development_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def reject_cross_origin_writes(request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin:
                origin_host = urlsplit(origin).netloc.lower()
                request_host = request.headers.get("host", "").lower()
                if (
                    origin_host != request_host
                    and (production_mode or origin not in development_origins)
                ):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "跨站请求已拒绝"},
                    )
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        return response

    resolved_limits = usage_limits or UsageLimits()

    @app.middleware("http")
    async def reject_oversized_uploads(request, call_next):
        if request.method == "POST" and request.url.path == "/api/documents":
            content_length = request.headers.get("content-length")
            max_request_bytes = (resolved_limits.max_document_mib + 2) * 1024 * 1024
            if (
                content_length
                and content_length.isdigit()
                and int(content_length) > max_request_bytes
            ):
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"单个文档不得超过 {resolved_limits.max_document_mib} MiB"
                        )
                    },
                )
        return await call_next(request)

    app.state.investigator = investigator or DemoInvestigator()
    app.state.ingestion = ingestion or InMemoryIngestion()
    app.state.evaluator = evaluator or DemoEvaluator()
    app.state.knowledge_bases = knowledge_bases or InMemoryKnowledgeBaseCatalog()
    app.state.tenant_access = tenant_access or OpenTenantAccess()
    app.state.secure_cookies = secure_cookies
    app.state.query_timeout_seconds = query_timeout_seconds
    app.state.runtime_config = runtime_config or {
        "mode": "local",
        "chat_provider": "local",
        "chat_base_url": None,
        "chat_model": "extractive",
        "embedding_provider": "local",
        "embedding_base_url": None,
        "embedding_model": "hashing",
        "embedding_dimensions": 384,
        "rerank_provider": "token_overlap",
        "query_timeout_seconds": query_timeout_seconds,
        "ocr_languages": "未启用",
        "max_document_mib": resolved_limits.max_document_mib,
        "max_batch_files": resolved_limits.max_batch_files,
        "max_knowledge_bases": resolved_limits.max_knowledge_bases,
        "max_organization_members": resolved_limits.max_organization_members,
        "query_limit_per_day": resolved_limits.query_per_day,
        "upload_limit_per_day": resolved_limits.upload_per_day,
        "evaluation_limit_per_hour": resolved_limits.evaluation_per_hour,
        "turnstile_enabled": bool(turnstile_site_key),
    }
    app.state.abuse_guard = abuse_guard or InMemoryAbuseGuard()
    app.state.usage_limits = resolved_limits
    app.state.turnstile_verifier = turnstile_verifier or DisabledTurnstileVerifier()
    app.state.turnstile_site_key = turnstile_site_key
    app.state.trust_proxy_headers = trust_proxy_headers
    app.include_router(router)
    return app


app = create_app()


def create_local_app(
    *,
    query_rewriter: QueryRewriter | None = None,
    composer: AnswerComposer | None = None,
    faithfulness_judge: FaithfulnessJudge | None = None,
    tenant_access: TenantAccess | None = None,
    query_timeout_seconds: float = 60,
    runtime_config: dict[str, str | int | float | None] | None = None,
    abuse_guard: AbuseGuard | None = None,
    usage_limits: UsageLimits | None = None,
    turnstile_verifier: TurnstileVerifier | None = None,
    turnstile_site_key: str = "",
) -> FastAPI:
    """Create a zero-dependency app that exercises the real RAG pipeline."""
    embedder = HashingEmbedder()
    index = InMemoryKnowledgeIndex()
    investigator = InvestigationEngine(
        query_rewriter=query_rewriter or IdentityQueryRewriter(),
        embedder=embedder,
        index=index,
        reranker=TokenOverlapReranker(),
        composer=composer or ExtractiveAnswerComposer(),
    )
    ingestion = InlineIngestionManager(
        parser=DocumentParser(),
        chunker=ParentChildChunker(),
        embedder=embedder,
        writer=index,
    )
    return create_app(
        investigator=investigator,
        ingestion=ingestion,
        evaluator=EvaluationEngine(
            investigator=investigator,
            faithfulness_judge=faithfulness_judge or HeuristicFaithfulnessJudge(),
        ),
        tenant_access=tenant_access,
        query_timeout_seconds=query_timeout_seconds,
        runtime_config=runtime_config,
        abuse_guard=abuse_guard,
        usage_limits=usage_limits,
        turnstile_verifier=turnstile_verifier,
        turnstile_site_key=turnstile_site_key,
    )
