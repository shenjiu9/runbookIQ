from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from runbookiq.security import UsageLimits

PROJECT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RUNBOOKIQ_",
        env_file=(PROJECT_ENV, ".env"),
        extra="ignore",
    )

    mode: str = Field(default="local", pattern="^(local|production)$")
    database_url: str = "postgresql+asyncpg://runbookiq:runbookiq@postgres:5432/runbookiq"
    ollama_base_url: str = "http://ollama:11434"
    chat_provider: str = Field(default="ollama", pattern="^(ollama|openai_compatible)$")
    chat_base_url: str = ""
    chat_api_key: SecretStr = SecretStr("")
    embedding_provider: str = Field(
        default="ollama",
        pattern="^(fastembed|ollama|openai_compatible)$",
    )
    embedding_base_url: str = ""
    embedding_api_key: SecretStr = SecretStr("")
    embedding_model: str = "nomic-embed-text"
    chat_model: str = "qwen2.5:7b"
    chat_thinking_enabled: bool | None = None
    chat_max_tokens: int | None = 1600
    query_timeout_seconds: float = 60
    rerank_provider: str = Field(default="chat", pattern="^(chat|token_overlap)$")
    ocr_languages: str = "chi_sim+eng"
    ocr_timeout_seconds: int = 30
    embedding_dimensions: int = 768
    fastembed_cache_dir: str = ".cache/fastembed"
    allowed_origins: str = "http://localhost:5173,http://localhost:8080"
    root_domain: str = "rag.xn--bang-fe6gk6c.top"
    secure_cookies: bool = True
    session_hours: int = Field(default=168, ge=1, le=24 * 90)
    turnstile_site_key: str = ""
    turnstile_secret_key: SecretStr = SecretStr("")
    turnstile_required: bool = False
    registration_limit_per_hour: int = Field(default=3, ge=1, le=100)
    registration_global_limit_per_hour: int = Field(default=30, ge=1, le=1000)
    login_limit_per_15_minutes: int = Field(default=10, ge=1, le=100)
    login_ip_limit_per_15_minutes: int = Field(default=40, ge=1, le=500)
    query_limit_per_minute: int = Field(default=20, ge=1, le=500)
    query_limit_per_day: int = Field(default=200, ge=1, le=10000)
    upload_limit_per_hour: int = Field(default=20, ge=1, le=500)
    upload_limit_per_day: int = Field(default=50, ge=1, le=5000)
    evaluation_limit_per_hour: int = Field(default=10, ge=1, le=500)
    invitation_limit_per_day: int = Field(default=20, ge=1, le=500)
    max_knowledge_bases: int = Field(default=5, ge=1, le=100)
    max_organization_members: int = Field(default=25, ge=1, le=1000)
    max_batch_files: int = Field(default=10, ge=1, le=100)
    max_document_mib: int = Field(default=20, ge=1, le=100)
    document_storage_path: str = ".data/documents"

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    def usage_limits(self) -> UsageLimits:
        return UsageLimits(
            registration_per_hour=self.registration_limit_per_hour,
            registration_global_per_hour=self.registration_global_limit_per_hour,
            login_per_15_minutes=self.login_limit_per_15_minutes,
            login_ip_per_15_minutes=self.login_ip_limit_per_15_minutes,
            query_per_minute=self.query_limit_per_minute,
            query_per_day=self.query_limit_per_day,
            upload_per_hour=self.upload_limit_per_hour,
            upload_per_day=self.upload_limit_per_day,
            evaluation_per_hour=self.evaluation_limit_per_hour,
            invitation_per_day=self.invitation_limit_per_day,
            max_knowledge_bases=self.max_knowledge_bases,
            max_organization_members=self.max_organization_members,
            max_batch_files=self.max_batch_files,
            max_document_mib=self.max_document_mib,
        )

    def public_runtime_config(self) -> dict[str, str | int | float | None]:
        """Return browser-safe runtime metadata without credentials."""
        return {
            "mode": self.mode,
            "chat_provider": self.chat_provider,
            "chat_base_url": self.chat_base_url or self.ollama_base_url,
            "chat_model": self.chat_model,
            "embedding_provider": self.embedding_provider,
            "embedding_base_url": (
                self.embedding_base_url
                or (self.ollama_base_url if self.embedding_provider == "ollama" else None)
            ),
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
            "rerank_provider": self.rerank_provider,
            "query_timeout_seconds": self.query_timeout_seconds,
            "ocr_languages": self.ocr_languages,
            "max_document_mib": self.max_document_mib,
            "max_batch_files": self.max_batch_files,
            "max_knowledge_bases": self.max_knowledge_bases,
            "max_organization_members": self.max_organization_members,
            "query_limit_per_day": self.query_limit_per_day,
            "upload_limit_per_day": self.upload_limit_per_day,
            "evaluation_limit_per_hour": self.evaluation_limit_per_hour,
            "turnstile_enabled": bool(
                self.turnstile_site_key
                and self.turnstile_secret_key.get_secret_value()
            ),
        }
