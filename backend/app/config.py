from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/knowledgehub"
    chroma_persist_dir: str = "./.chroma"
    llm_provider: str = "openai"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"
    chat_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
