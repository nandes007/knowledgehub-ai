from app.config import Settings


def test_database_url_reads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@host:5432/db")
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_database_url_has_a_local_default():
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql+psycopg://")
