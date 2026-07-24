import asyncio

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status

from runbookiq.api.schemas import EvaluationRunRequest, KnowledgeBaseCreate, QueryRequest
from runbookiq.domain.models import Answer, EvaluationReport, IngestionJob, KnowledgeBase
from runbookiq.evaluation.benchmark import load_benchmark

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _require_knowledge_base(request: Request, knowledge_base_id: str) -> None:
    try:
        await request.app.state.knowledge_bases.get(knowledge_base_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="知识库不存在") from exc


@router.post(
    "/knowledge-bases",
    response_model=KnowledgeBase,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    request: Request,
) -> KnowledgeBase:
    return await request.app.state.knowledge_bases.create(
        name=payload.name,
        description=payload.description,
    )


@router.get("/knowledge-bases", response_model=list[KnowledgeBase])
async def list_knowledge_bases(request: Request) -> list[KnowledgeBase]:
    return await request.app.state.knowledge_bases.list()


@router.delete(
    "/knowledge-bases/{knowledge_base_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_knowledge_base(knowledge_base_id: str, request: Request) -> Response:
    try:
        await request.app.state.knowledge_bases.delete(knowledge_base_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="知识库不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        return await request.app.state.ingestion.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ingestion job not found") from exc


@router.post("/evaluations/run", response_model=EvaluationReport)
async def run_evaluation(
    payload: EvaluationRunRequest,
    request: Request,
) -> EvaluationReport:
    await _require_knowledge_base(request, payload.knowledge_base_id)
    if payload.suite_id:
        try:
            cases, suite_total = load_benchmark(
                payload.suite_id,
                max_cases=payload.max_cases,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="evaluation suite not found") from exc
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
async def latest_evaluation(request: Request) -> EvaluationReport | None:
    return await request.app.state.evaluator.latest()
