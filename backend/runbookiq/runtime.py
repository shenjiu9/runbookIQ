from sqlalchemy.ext.asyncio import create_async_engine

from runbookiq.adapters.fastembed_provider import FastEmbedClient
from runbookiq.adapters.generation import ChatAnswerComposer, ChatQueryRewriter
from runbookiq.adapters.knowledge_bases import PostgresKnowledgeBaseCatalog
from runbookiq.adapters.local import TokenOverlapReranker
from runbookiq.adapters.ollama import OllamaClient
from runbookiq.adapters.openai_compatible import (
    OpenAICompatibleChatClient,
    OpenAICompatibleEmbeddingClient,
)
from runbookiq.adapters.postgres import PostgresKnowledgeIndex
from runbookiq.adapters.reranking import ChatReranker
from runbookiq.adapters.tenancy import PostgresTenantAccess
from runbookiq.app import create_app, create_local_app
from runbookiq.evaluation.engine import ChatFaithfulnessJudge, EvaluationEngine
from runbookiq.ingestion.chunker import ParentChildChunker
from runbookiq.ingestion.manager import InlineIngestionManager
from runbookiq.ingestion.parser import DocumentParser, TesseractOcrEngine
from runbookiq.investigation.engine import InvestigationEngine
from runbookiq.security import CloudflareTurnstileVerifier, PostgresAbuseGuard
from runbookiq.settings import Settings


def build_app():
    settings = Settings()
    if settings.mode == "local":
        if (
            settings.chat_provider == "openai_compatible"
            and settings.chat_base_url
            and settings.chat_api_key.get_secret_value()
        ):
            chat = OpenAICompatibleChatClient(
                base_url=settings.chat_base_url,
                api_key=settings.chat_api_key.get_secret_value(),
                model=settings.chat_model,
                thinking_enabled=settings.chat_thinking_enabled,
                max_tokens=settings.chat_max_tokens,
            )
            return create_local_app(
                query_rewriter=ChatQueryRewriter(chat),
                composer=ChatAnswerComposer(chat),
                faithfulness_judge=ChatFaithfulnessJudge(chat),
                query_timeout_seconds=settings.query_timeout_seconds,
                runtime_config=settings.public_runtime_config(),
            )
        return create_local_app()

    database = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    ollama = None
    if settings.chat_provider == "ollama" or settings.embedding_provider == "ollama":
        ollama = OllamaClient(
            base_url=settings.ollama_base_url,
            chat_model=settings.chat_model,
            embedding_model=settings.embedding_model,
        )

    if settings.chat_provider == "ollama":
        assert ollama is not None
        chat = ollama
    else:
        if not settings.chat_base_url or not settings.chat_api_key.get_secret_value():
            raise ValueError(
                "RUNBOOKIQ_CHAT_BASE_URL and RUNBOOKIQ_CHAT_API_KEY are required "
                "for openai_compatible chat"
            )
        chat = OpenAICompatibleChatClient(
            base_url=settings.chat_base_url,
            api_key=settings.chat_api_key.get_secret_value(),
            model=settings.chat_model,
            thinking_enabled=settings.chat_thinking_enabled,
            max_tokens=settings.chat_max_tokens,
        )

    if settings.embedding_provider == "fastembed":
        embedder = FastEmbedClient(
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            cache_dir=settings.fastembed_cache_dir,
        )
    elif settings.embedding_provider == "ollama":
        assert ollama is not None
        embedder = ollama
    else:
        if (
            not settings.embedding_base_url
            or not settings.embedding_api_key.get_secret_value()
        ):
            raise ValueError(
                "RUNBOOKIQ_EMBEDDING_BASE_URL and RUNBOOKIQ_EMBEDDING_API_KEY are required "
                "for openai_compatible embeddings"
            )
        embedder = OpenAICompatibleEmbeddingClient(
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key.get_secret_value(),
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

    index = PostgresKnowledgeIndex(database)
    knowledge_bases = PostgresKnowledgeBaseCatalog(database)
    tenant_access = PostgresTenantAccess(
        database,
        root_domain=settings.root_domain,
        session_hours=settings.session_hours,
    )
    investigator = InvestigationEngine(
        query_rewriter=ChatQueryRewriter(chat),
        embedder=embedder,
        index=index,
        reranker=(
            ChatReranker(chat)
            if settings.rerank_provider == "chat"
            else TokenOverlapReranker()
        ),
        composer=ChatAnswerComposer(chat),
    )
    ingestion = InlineIngestionManager(
        parser=DocumentParser(
            ocr_engine=TesseractOcrEngine(
                languages=settings.ocr_languages,
                timeout_seconds=settings.ocr_timeout_seconds,
            )
        ),
        chunker=ParentChildChunker(),
        embedder=embedder,
        writer=index,
    )
    evaluator = EvaluationEngine(
        investigator=investigator,
        faithfulness_judge=ChatFaithfulnessJudge(chat),
    )
    return create_app(
        investigator=investigator,
        ingestion=ingestion,
        evaluator=evaluator,
        knowledge_bases=knowledge_bases,
        tenant_access=tenant_access,
        query_timeout_seconds=settings.query_timeout_seconds,
        runtime_config=settings.public_runtime_config(),
        secure_cookies=settings.secure_cookies,
        production_mode=True,
        allowed_hosts=[
            settings.root_domain,
            f"*.{settings.root_domain}",
            "api",
            "localhost",
            "127.0.0.1",
        ],
        abuse_guard=PostgresAbuseGuard(database),
        usage_limits=settings.usage_limits(),
        turnstile_verifier=CloudflareTurnstileVerifier(
            secret_key=settings.turnstile_secret_key.get_secret_value(),
            expected_hostname=settings.root_domain,
            required=settings.turnstile_required,
        ),
        turnstile_site_key=settings.turnstile_site_key,
        trust_proxy_headers=True,
    )


app = build_app()
