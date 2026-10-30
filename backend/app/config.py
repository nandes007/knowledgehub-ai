from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root .env, regardless of the process's cwd (e.g. `uv run` from `backend/`).
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/knowledgehub"
    # Set QDRANT_URL to use a Qdrant server; leave empty for embedded Qdrant at qdrant_path.
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_path: str = "./.qdrant"
    llm_provider: str = "openai"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"
    chat_model: str = "gpt-4o-mini"
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "./uploads"
    # Set S3_BUCKET to store uploads in S3; leave empty to use upload_dir.
    s3_bucket: str = ""
    s3_prefix: str = "knowledgehub/"
    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    max_upload_size_mb: int = 25
    jwt_secret: str = "change-me-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    hybrid_search: bool = True

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
