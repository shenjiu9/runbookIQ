import asyncio

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status

from runbookiq.api.schemas import (
    EvaluationRunRequest,
    KnowledgeBaseCreate,
    LoginRequest,
    QueryRequest,
    RegistrationRequest,
    RuntimeConfigResponse,
)
from runbookiq.domain.models import (
    Answer,
    EvaluationReport,
    EvaluationSuite,
    IngestionJob,
    KnowledgeBase,
)
from runbookiq.domain.tenancy import TenantContext, TenantSession
from runbookiq.evaluation.benchmark import get_benchmark, list_benchmarks, load_benchmark

router = APIRouter(prefix="/api")
SESSION_COOKIE = "runbookiq_session"
CSRF_COOKIE = "runbookiq_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/runtime-config", response_model=RuntimeConfigResponse)
async def runtime_config(request: Request) -> RuntimeConfigResponse:
    return RuntimeConfigResponse.model_validate(request.app.state.runtime_config)


async def _current_tenant(request: Request) -> TenantContext:
    session_token = request.cookies.get(SESSION_COOKIE)
    context = await request.app.state.tenant_access.resolve(
        session_token=session_token,
        host=request.headers.get("host", ""),
    )
    if context is None:
        raise HTTPException(status_code=401, detail="请先登录")
    if request.method not in SAFE_METHODS:
        csrf_valid = await request.app.state.tenant_access.validate_csrf(
            session_token,
            request.headers.get("x-csrf-token"),
        )
        if not csrf_valid:
            raise HTTPException(status_code=403, detail="CSRF 校验失败")
    return context


def _set_session_cookie(
    response: Response,
    session: TenantSession,
    request: Request,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session.token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=request.app.state.secure_cookies,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=session.csrf_token,
        max_age=7 * 24 * 60 * 60,
        httponly=False,
        secure=request.app.state.secure_cookies,
        samesite="lax",
        path="/",
    )


@router.post(
    "/auth/register",
    response_model=TenantContext,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegistrationRequest,
    request: Request,
    response: Response,
) -> TenantContext:
    if not request.app.state.tenant_access.authentication_required:
        raise HTTPException(status_code=409, detail="当前环境未启用注册")
    try:
        session = await request.app.state.tenant_access.register(
            email=payload.email,
            password=payload.password,
            organization_name=payload.organization_name,
            slug=payload.slug,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_session_cookie(response, session, request)
    return session.context


@router.post("/auth/login", response_model=TenantContext)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> TenantContext:
    try:
        session = await request.app.state.tenant_access.authenticate(
            email=payload.email,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_session_cookie(response, session, request)
    return session.context


@router.get("/auth/me", response_model=TenantContext)
async def current_user(request: Request) -> TenantContext:
    return await _current_tenant(request)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> Response:
    session_token = request.cookies.get(SESSION_COOKIE)
    if request.app.state.tenant_access.authentication_required:
        csrf_valid = await request.app.state.tenant_access.validate_csrf(
            session_token,
            request.headers.get("x-csrf-token"),
        )
        if not csrf_valid:
            raise HTTPException(status_code=403, detail="CSRF 校验失败")
    await request.app.state.tenant_access.revoke_session(
        session_token
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/internal/tls/allow")
async def allow_tenant_tls(domain: str, request: Request) -> dict[str, bool]:
    if not await request.app.state.tenant_access.domain_allowed(domain):
        raise HTTPException(status_code=403, detail="domain is not registered")
    return {"allowed": True}


async def _require_knowledge_base(
    request: Request,
    knowledge_base_id: str,
    context: TenantContext | None = None,
) -> TenantContext:
    actual_context = context or await _current_tenant(request)
    try:
        await request.app.state.knowledge_bases.get(knowledge_base_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="知识库不存在") from exc
    if not await request.app.state.tenant_access.can_access_knowledge_base(
        actual_context,
        knowledge_base_id,
    ):
        raise HTTPException(status_code=404, detail="知识库不存在")
    return actual_context


@router.post(
    "/knowledge-bases",
    response_model=KnowledgeBase,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    request: Request,
) -> KnowledgeBase:
    context = await _current_tenant(request)
    knowledge_base = await request.app.state.knowledge_bases.create(
        name=payload.name,
        description=payload.description,
    )
    await request.app.state.tenant_access.grant_knowledge_base(
        context,
        knowledge_base.id,
    )
    return knowledge_base


@router.get("/knowledge-bases", response_model=list[KnowledgeBase])
async def list_knowledge_bases(request: Request) -> list[KnowledgeBase]:
    context = await _current_tenant(request)
    allowed_ids = await request.app.state.tenant_access.allowed_knowledge_base_ids(context)
    knowledge_bases = await request.app.state.knowledge_bases.list()
    if allowed_ids is None:
        return knowledge_bases
    return [item for item in knowledge_bases if item.id in allowed_ids]


@router.delete(
    "/knowledge-bases/{knowledge_base_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_knowledge_base(knowledge_base_id: str, request: Request) -> Response:
    context = await _require_knowledge_base(request, knowledge_base_id)
    try:
        await request.app.state.knowledge_bases.delete(knowledge_base_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="知识库不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await request.app.state.tenant_access.revoke_knowledge_base(
        context,
        knowledge_base_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/knowledge-bases/{knowledge_base_id}/evaluation-suites",
    response_model=list[EvaluationSuite],
)
async def list_evaluation_suites(
    knowledge_base_id: str,
    request: Request,
) -> list[EvaluationSuite]:
    await _require_knowledge_base(request, knowledge_base_id)
    return list_benchmarks(knowledge_base_id)


@router.post("/query", response_model=Answer)
async def query(payload: QueryRequest, request: Request) -> Answer:
    await _require_knowledge_base(request, payload.knowledge_base_id)
    try:
        async with asyncio.timeout(request.app.state.query_timeout_seconds):
            return await request.app.state.investigator.ask(
                knowledge_base_id=payload.knowledge_base_id,
                question=payload.question,
            )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="模型响应超时，请稍后重试。",
        ) from exc


@router.post(
    "/documents",
    response_model=IngestionJob,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    request: Request,
    knowledge_base_id: str = Form(...),
    file: UploadFile = File(...),  # noqa: B008 - FastAPI dependency declaration
) -> IngestionJob:
    await _require_knowledge_base(request, knowledge_base_id)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="document must not be empty")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="document exceeds 20 MiB")
    return await request.app.state.ingestion.submit(
        knowledge_base_id=knowledge_base_id,
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
        content=content,
    )


@router.get("/ingestion/jobs/{job_id}", response_model=IngestionJob)
async def get_ingestion_job(job_id: str, request: Request) -> IngestionJob:
    try:
        job = await request.app.state.ingestion.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ingestion job not found") from exc
    await _require_knowledge_base(request, job.knowledge_base_id)
    return job


@router.post("/evaluations/run", response_model=EvaluationReport)
async def run_evaluation(
    payload: EvaluationRunRequest,
    request: Request,
) -> EvaluationReport:
    await _require_knowledge_base(request, payload.knowledge_base_id)
    if payload.suite_id:
        try:
            suite = get_benchmark(payload.suite_id)
            cases, suite_total = load_benchmark(
                payload.suite_id,
                max_cases=payload.max_cases,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="evaluation suite not found") from exc
        if suite.knowledge_base_id != payload.knowledge_base_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该评测集不属于当前知识库，已禁止运行",
            )
        suite_id = payload.suite_id
    else:
        cases = [case.model_dump(exclude_none=True) for case in payload.cases or []]
        suite_total = len(cases)
        suite_id = "custom"
    return await request.app.state.evaluator.run(
        knowledge_base_id=payload.knowledge_base_id,
        cases=cases,
        suite_id=suite_id,
        suite_total=suite_total,
    )


@router.get("/evaluations/latest", response_model=EvaluationReport | None)
async def latest_evaluation(
    knowledge_base_id: str,
    request: Request,
) -> EvaluationReport | None:
    await _require_knowledge_base(request, knowledge_base_id)
    return await request.app.state.evaluator.latest(knowledge_base_id)
