from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

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
            "max_document_mib": 20,
        }
