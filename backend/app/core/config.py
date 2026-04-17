from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    postgres_db: Optional[str] = None
    REDIS_URL: Optional[str] = None
    GEMINI_MODEL: str
    GEMINI_API_KEY: str
    EMBEDDING_MODEL: str
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()