import asyncio
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status

from runbookiq.api.schemas import (
    EvaluationRunRequest,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationPreviewRequest,
    KnowledgeBaseCreate,
    LoginRequest,
    OrganizationBrandingUpdate,
    QueryRequest,
    RegistrationRequest,
    RuntimeConfigResponse,
    SecurityConfigResponse,
)
from runbookiq.domain.models import (
    Answer,
    EvaluationReport,
    EvaluationSuite,
    IngestionJob,
    KnowledgeBase,
    SourceDocument,
)
from runbookiq.domain.tenancy import (
    CreatedTenantInvitation,
    OrganizationBranding,
    OrganizationMember,
    TenantContext,
    TenantInvitation,
    TenantInvitationPreview,
    TenantRole,
    TenantSession,
)
from runbookiq.evaluation.benchmark import get_benchmark, list_benchmarks, load_benchmark
from runbookiq.security import RateLimitExceeded

router = APIRouter(prefix="/api")
SESSION_COOKIE = "runbookiq_session"
CSRF_COOKIE = "runbookiq_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ALLOWED_UPLOAD_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/runtime-config", response_model=RuntimeConfigResponse)
async def runtime_config(request: Request) -> RuntimeConfigResponse:
    return RuntimeConfigResponse.model_validate(request.app.state.runtime_config)


@router.get("/security-config", response_model=SecurityConfigResponse)
async def security_config(request: Request) -> SecurityConfigResponse:
    verifier = request.app.state.turnstile_verifier
    limits = request.app.state.usage_limits
    enabled = bool(verifier.enabled and request.app.state.turnstile_site_key)
    return SecurityConfigResponse(
        turnstile_enabled=enabled,
        turnstile_required=bool(verifier.required),
        turnstile_site_key=request.app.state.turnstile_site_key if enabled else None,
        max_batch_files=limits.max_batch_files,
        max_document_mib=limits.max_document_mib,
    )


def _client_ip(request: Request) -> str:
    if request.app.state.trust_proxy_headers:
        cloudflare_ip = request.headers.get("cf-connecting-ip")
        if cloudflare_ip:
            return cloudflare_ip.strip()
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"


async def _enforce_limit(
    request: Request,
    *,
    action: str,
    scope: str,
    limit: int,
    window_seconds: int,
    detail: str,
) -> None:
    try:
        await request.app.state.abuse_guard.enforce(
            action=action,
            scope=scope,
            limit=limit,
            window_seconds=window_seconds,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


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


def _require_role(context: TenantContext, *allowed_roles: TenantRole) -> None:
    if context.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="当前角色无权执行此操作")


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
    limits = request.app.state.usage_limits
    client_ip = _client_ip(request)
    await _enforce_limit(
        request,
        action="registration-ip",
        scope=client_ip,
        limit=limits.registration_per_hour,
        window_seconds=60 * 60,
        detail="注册请求过于频繁，请一小时后再试",
    )
    if not await request.app.state.turnstile_verifier.verify(
        token=payload.turnstile_token,
        remote_ip=client_ip,
        action="register",
    ):
        raise HTTPException(status_code=400, detail="人机验证未通过，请刷新后重试")
    await _enforce_limit(
        request,
        action="registration-global",
        scope="all",
        limit=limits.registration_global_per_hour,
        window_seconds=60 * 60,
        detail="当前注册人数较多，请稍后再试",
    )
    try:
        session = await request.app.state.tenant_access.register(
            email=payload.email,
            password=payload.password,
            organization_name=payload.organization_name,
            slug=payload.slug,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    default_knowledge_base = await request.app.state.knowledge_bases.create(
        name=f"{session.context.organization.name} 企业知识库",
        description="企业制度、手册与业务资料",
    )
    await request.app.state.tenant_access.grant_knowledge_base(
        session.context,
        default_knowledge_base.id,
    )
    _set_session_cookie(response, session, request)
    return session.context


@router.post("/auth/login", response_model=TenantContext)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> TenantContext:
    limits = request.app.state.usage_limits
    client_ip = _client_ip(request)
    await _enforce_limit(
        request,
        action="login-ip",
        scope=client_ip,
        limit=limits.login_ip_per_15_minutes,
        window_seconds=15 * 60,
        detail="登录尝试过于频繁，请稍后再试",
    )
    await _enforce_limit(
        request,
        action="login-account",
        scope=payload.email.lower(),
        limit=limits.login_per_15_minutes,
        window_seconds=15 * 60,
        detail="此账号登录尝试过多，请 15 分钟后再试",
    )
    try:
        session = await request.app.state.tenant_access.authenticate(
            email=payload.email,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    resolved_context = await request.app.state.tenant_access.resolve(
        session_token=session.token,
        host=request.headers.get("host", ""),
    )
    if resolved_context is None:
        await request.app.state.tenant_access.revoke_session(session.token)
        raise HTTPException(status_code=403, detail="该账号不属于当前企业网址")
    _set_session_cookie(response, session, request)
    return session.context


@router.post(
    "/auth/invitations/preview",
    response_model=TenantInvitationPreview,
)
async def preview_invitation(
    payload: InvitationPreviewRequest,
    request: Request,
) -> TenantInvitationPreview:
    await _enforce_limit(
        request,
        action="invitation-preview",
        scope=_client_ip(request),
        limit=request.app.state.usage_limits.invitation_preview_per_15_minutes,
        window_seconds=15 * 60,
        detail="邀请链接检查过于频繁，请稍后再试",
    )
    try:
        return await request.app.state.tenant_access.preview_invitation(payload.token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/auth/invitations/accept", response_model=TenantContext)
async def accept_invitation(
    payload: InvitationAcceptRequest,
    request: Request,
    response: Response,
) -> TenantContext:
    await _enforce_limit(
        request,
        action="invitation-accept",
        scope=_client_ip(request),
        limit=10,
        window_seconds=60 * 60,
        detail="接受邀请尝试过于频繁，请稍后再试",
    )
    try:
        session = await request.app.state.tenant_access.accept_invitation(
            token=payload.token,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_session_cookie(response, session, request)
    return session.context


@router.get("/auth/me", response_model=TenantContext)
async def current_user(request: Request) -> TenantContext:
    return await _current_tenant(request)


@router.get(
    "/organization/members",
    response_model=list[OrganizationMember],
)
async def list_organization_members(request: Request) -> list[OrganizationMember]:
    context = await _current_tenant(request)
    return await request.app.state.tenant_access.list_members(context)


@router.get(
    "/organization/branding",
    response_model=OrganizationBranding,
)
async def get_organization_branding(request: Request) -> OrganizationBranding:
    context = await _current_tenant(request)
    return await request.app.state.tenant_access.get_branding(context)


@router.patch(
    "/organization/branding",
    response_model=OrganizationBranding,
)
async def update_organization_branding(
    payload: OrganizationBrandingUpdate,
    request: Request,
) -> OrganizationBranding:
    context = await _current_tenant(request)
    _require_role(context, "owner", "admin")
    return await request.app.state.tenant_access.update_branding(
        context,
        OrganizationBranding.model_validate(payload.model_dump()),
    )


@router.get(
    "/organization/invitations",
    response_model=list[TenantInvitation],
)
async def list_organization_invitations(request: Request) -> list[TenantInvitation]:
    context = await _current_tenant(request)
    _require_role(context, "owner", "admin")
    return await request.app.state.tenant_access.list_invitations(context)


@router.post(
    "/organization/invitations",
    response_model=CreatedTenantInvitation,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_invitation(
    payload: InvitationCreateRequest,
    request: Request,
) -> CreatedTenantInvitation:
    context = await _current_tenant(request)
    _require_role(context, "owner", "admin")
    limits = request.app.state.usage_limits
    await _enforce_limit(
        request,
        action="organization-invitation",
        scope=context.organization.id,
        limit=limits.invitation_per_day,
        window_seconds=24 * 60 * 60,
        detail="今日邀请数量已达上限，请明天再试",
    )
    members = await request.app.state.tenant_access.list_members(context)
    invitations = await request.app.state.tenant_access.list_invitations(context)
    if len(members) + len(invitations) >= limits.max_organization_members:
        raise HTTPException(
            status_code=409,
            detail=f"当前版本每个企业最多 {limits.max_organization_members} 名成员（含待接受邀请）",
        )
    try:
        return await request.app.state.tenant_access.create_invitation(
            context,
            email=payload.email,
            role=payload.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/organization/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_organization_invitation(
    invitation_id: str,
    request: Request,
) -> Response:
    context = await _current_tenant(request)
    _require_role(context, "owner", "admin")
    try:
        await request.app.state.tenant_access.revoke_invitation(
            context,
            invitation_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="邀请不存在") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    _require_role(context, "owner", "admin", "editor")
    allowed_ids = await request.app.state.tenant_access.allowed_knowledge_base_ids(context)
    current_count = len(allowed_ids or [])
    max_knowledge_bases = request.app.state.usage_limits.max_knowledge_bases
    if allowed_ids is not None and current_count >= max_knowledge_bases:
        raise HTTPException(
            status_code=409,
            detail=f"当前版本每个企业最多创建 {max_knowledge_bases} 个知识库",
        )
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
    _require_role(context, "owner", "admin")
    documents = await request.app.state.ingestion.list_documents(knowledge_base_id)
    try:
        await request.app.state.knowledge_bases.delete(knowledge_base_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="知识库不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    for document in documents:
        try:
            await request.app.state.ingestion.delete_document(
                knowledge_base_id=knowledge_base_id,
                document_id=document.id,
            )
        except KeyError:
            # PostgreSQL cascades document rows with the knowledge base. Its
            # deletion trigger has already queued the original for cleanup.
            continue
    await request.app.state.ingestion.cleanup_pending_objects()
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
    context = await _require_knowledge_base(request, payload.knowledge_base_id)
    limits = request.app.state.usage_limits
    await _enforce_limit(
        request,
        action="query-user-minute",
        scope=context.user.id,
        limit=limits.query_per_minute,
        window_seconds=60,
        detail="提问速度过快，请稍后再试",
    )
    await _enforce_limit(
        request,
        action="query-organization-day",
        scope=context.organization.id,
        limit=limits.query_per_day,
        window_seconds=24 * 60 * 60,
        detail=f"企业今日问答次数已达 {limits.query_per_day} 次上限",
    )
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


def _safe_upload_filename(original: str | None) -> str:
    filename = (original or "untitled").replace("\\", "/").rsplit("/", 1)[-1]
    filename = filename.replace("\x00", "").strip()
    if not filename:
        filename = "untitled"
    return filename[:255]


async def _read_upload_limited(file: UploadFile, *, max_bytes: int) -> bytes:
    content = bytearray()
    try:
        while chunk := await file.read(1024 * 1024):
            content.extend(chunk)
            if len(content) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"单个文档不得超过 {max_bytes // (1024 * 1024)} MiB",
                )
    finally:
        await file.close()
    return bytes(content)


def _validate_upload_signature(suffix: str, content: bytes) -> None:
    valid = True
    if suffix == ".pdf":
        valid = content.lstrip().startswith(b"%PDF-")
    elif suffix == ".docx":
        valid = content.startswith(b"PK")
    elif suffix == ".png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif suffix in {".jpg", ".jpeg"}:
        valid = content.startswith(b"\xff\xd8\xff")
    elif suffix == ".webp":
        valid = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    elif suffix == ".bmp":
        valid = content.startswith(b"BM")
    elif suffix in {".tif", ".tiff"}:
        valid = content.startswith((b"II*\x00", b"MM\x00*"))
    if not valid:
        raise HTTPException(status_code=422, detail="文件内容与扩展名不匹配")


async def _enforce_document_upload_limits(
    request: Request,
    context: TenantContext,
) -> None:
    limits = request.app.state.usage_limits
    await _enforce_limit(
        request,
        action="upload-user-hour",
        scope=context.user.id,
        limit=limits.upload_per_hour,
        window_seconds=60 * 60,
        detail="上传频率过高，请稍后再试",
    )
    await _enforce_limit(
        request,
        action="upload-organization-day",
        scope=context.organization.id,
        limit=limits.upload_per_day,
        window_seconds=24 * 60 * 60,
        detail=f"企业今日上传数量已达 {limits.upload_per_day} 份上限",
    )


async def _validated_document_upload(
    request: Request,
    file: UploadFile,
) -> tuple[str, str, bytes]:
    filename = _safe_upload_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        await file.close()
        raise HTTPException(status_code=415, detail="不支持此文件格式")
    content = await _read_upload_limited(
        file,
        max_bytes=request.app.state.usage_limits.max_document_mib * 1024 * 1024,
    )
    if not content:
        raise HTTPException(status_code=422, detail="文档内容不能为空")
    _validate_upload_signature(suffix, content)
    return filename, file.content_type or "application/octet-stream", content


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
    context = await _require_knowledge_base(request, knowledge_base_id)
    _require_role(context, "owner", "admin", "editor")
    await _enforce_document_upload_limits(request, context)
    filename, content_type, content = await _validated_document_upload(request, file)
    return await request.app.state.ingestion.submit(
        knowledge_base_id=knowledge_base_id,
        filename=filename,
        content_type=content_type,
        content=content,
    )


@router.get(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=list[SourceDocument],
)
async def list_documents(
    knowledge_base_id: str,
    request: Request,
) -> list[SourceDocument]:
    await _require_knowledge_base(request, knowledge_base_id)
    return await request.app.state.ingestion.list_documents(knowledge_base_id)


@router.put(
    "/knowledge-bases/{knowledge_base_id}/documents/{document_id}",
    response_model=IngestionJob,
)
async def replace_document(
    knowledge_base_id: str,
    document_id: str,
    request: Request,
    file: UploadFile = File(...),  # noqa: B008 - FastAPI dependency declaration
) -> IngestionJob:
    context = await _require_knowledge_base(request, knowledge_base_id)
    _require_role(context, "owner", "admin", "editor")
    await _enforce_document_upload_limits(request, context)
    filename, content_type, content = await _validated_document_upload(request, file)
    try:
        return await request.app.state.ingestion.replace(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            filename=filename,
            content_type=content_type,
            content=content,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="文档不存在") from exc


@router.delete(
    "/knowledge-bases/{knowledge_base_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    knowledge_base_id: str,
    document_id: str,
    request: Request,
) -> Response:
    context = await _require_knowledge_base(request, knowledge_base_id)
    _require_role(context, "owner", "admin", "editor")
    try:
        await request.app.state.ingestion.delete_document(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="文档不存在") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/knowledge-bases/{knowledge_base_id}/documents/{document_id}/content",
)
async def download_document(
    knowledge_base_id: str,
    document_id: str,
    request: Request,
) -> Response:
    await _require_knowledge_base(request, knowledge_base_id)
    try:
        document, content = await request.app.state.ingestion.get_document_content(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="文档原件不存在") from exc
    return Response(
        content=content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": (
                "attachment; filename*=UTF-8''" + quote(document.filename)
            ),
            "Cache-Control": "private, no-store",
        },
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
    context = await _require_knowledge_base(request, payload.knowledge_base_id)
    _require_role(context, "owner", "admin", "editor")
    limits = request.app.state.usage_limits
    await _enforce_limit(
        request,
        action="evaluation-organization-hour",
        scope=context.organization.id,
        limit=limits.evaluation_per_hour,
        window_seconds=60 * 60,
        detail=f"企业每小时最多运行 {limits.evaluation_per_hour} 次评测",
    )
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
