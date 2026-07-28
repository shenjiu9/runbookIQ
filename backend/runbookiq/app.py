from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from runbookiq.adapters.demo import DemoEvaluator, DemoInvestigator, InMemoryIngestion
from runbookiq.adapters.knowledge_bases import InMemoryKnowledgeBaseCatalog
from runbookiq.adapters.local import (
    ExtractiveAnswerComposer,
    HashingEmbedder,
    IdentityQueryRewriter,
    InMemoryKnowledgeIndex,
    TokenOverlapReranker,
)
from runbookiq.api.routes import router
from runbookiq.domain.ports import (
    Evaluator,
    IngestionManager,
    Investigator,
    KnowledgeBaseCatalog,
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


def create_app(
    *,
    investigator: Investigator | None = None,
    ingestion: IngestionManager | None = None,
    evaluator: Evaluator | None = None,
    knowledge_bases: KnowledgeBaseCatalog | None = None,
    query_timeout_seconds: float = 60,
    runtime_config: dict[str, str | int | float | None] | None = None,
) -> FastAPI:
    app = FastAPI(
        title="RunbookIQ",
        version="0.1.0",
        description="Incident investigation RAG workbench",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.investigator = investigator or DemoInvestigator()
    app.state.ingestion = ingestion or InMemoryIngestion()
    app.state.evaluator = evaluator or DemoEvaluator()
    app.state.knowledge_bases = knowledge_bases or InMemoryKnowledgeBaseCatalog()
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
        "max_document_mib": 20,
    }
    app.include_router(router)
    return app


app = create_app()


def create_local_app(
    *,
    query_rewriter: QueryRewriter | None = None,
    composer: AnswerComposer | None = None,
    faithfulness_judge: FaithfulnessJudge | None = None,
    query_timeout_seconds: float = 60,
    runtime_config: dict[str, str | int | float | None] | None = None,
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
        query_timeout_seconds=query_timeout_seconds,
        runtime_config=runtime_config,
    )
