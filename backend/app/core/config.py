from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# CORS origins
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5500",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5500",
]


class Settings(BaseSettings):
    # Application
    app_name: str = "Multi-Agent Job Assistant"
    app_version: str = "0.1.0"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    api_prefix: str = Field(
        default="/api/v1",
        validation_alias="API_V1_PREFIX",
    )

    # Logging
    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"
    log_format: Literal["console", "json"] = "console"

    # CORS
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: DEFAULT_CORS_ORIGINS.copy(),
    )
    backend_cors_allow_credentials: bool = True

    # LLM
    llm_provider: Literal["openai", "9router"] = "openai"
    llm_model: str = "gpt-5-mini"
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_structured_output_method: Literal[
        "json_schema",
        "function_calling",
    ] = "function_calling"

    openai_api_key: str | None = Field(default=None, repr=False)
    openai_base_url: str | None = Field(default=None, repr=False)

    nine_router_api_key: str | None = Field(default=None, repr=False)
    nine_router_base_url: str | None = Field(default=None, repr=False)

    max_cv_text_chars: int = Field(default=100_000, ge=1_000, le=500_000)

    # LangSmith
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = Field(default=None, repr=False)
    langsmith_project: str = "multi-agent-job-assistant"

    # Job storage
    job_storage_backend: Literal["jsonl", "postgres"] = "jsonl"
    job_database_url: str | None = Field(default=None, repr=False)
    job_database_pool_size: int = Field(default=5, ge=1, le=50)
    job_database_max_overflow: int = Field(default=10, ge=0, le=100)
    job_database_echo: bool = False

    # File upload
    max_upload_size_mb: int = 10
    allowed_cv_content_types: tuple[str, ...] = ("application/pdf",)
    storage_dir: Path = Path("storage")
    upload_dir: Path = Path("storage/uploads")
    upload_chunk_size_bytes: int = Field(default=1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=20, ge=1, le=100)
    min_native_text_chars_per_page: int = Field(default=50, ge=0, le=1000)

    # OCR
    ocr_dpi: int = Field(default=250, ge=150, le=400)
    ocr_min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Pydantic settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Job embeddings 
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimensions: int = Field(default=1024, ge=1024, le=1024)
    embedding_device: Literal["cpu", "cuda"] = "cpu"
    embedding_batch_size: int = Field(default=4, ge=1, le=32)
    embedding_max_length: int = Field(default=2048, ge=128, le=8192)
    embedding_cache_dir: Path = Path("storage/models")
    job_embedding_max_chars: int = Field(default=12_000, ge=1_000, le=50_000)

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = Field(default=None, repr=False)
    qdrant_collection_name: str = "jobs_bge_m3_v1"
    qdrant_timeout_seconds: float = Field(default=30.0, gt=0)

    # Conversation Memory
    conversation_memory_backend: Literal[
        "memory",
        "postgres",
    ] = "memory"
    conversation_memory_pool_size: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    # Upload size conversion
    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    # CORS validation
    @field_validator("backend_cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        normalized_origins: list[str] = []

        for origin in origins:
            normalized_origin = origin.rstrip("/")
            parsed_origin = urlsplit(normalized_origin)

            is_invalid = (
                normalized_origin == "*"
                or parsed_origin.scheme not in {"http", "https"}
                or not parsed_origin.netloc
                or bool(parsed_origin.path)
                or bool(parsed_origin.query)
                or bool(parsed_origin.fragment)
            )

            if is_invalid:
                raise ValueError(f"Invalid CORS origin: {origin}")

            normalized_origins.append(normalized_origin)

        return list(dict.fromkeys(normalized_origins))


# Cached settings
@lru_cache
def get_settings() -> Settings:
    return Settings()