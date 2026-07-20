from pathlib import Path

from app.config import Settings


def test_database_url_reads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@host:5432/db")
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_database_url_has_a_local_default():
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_env_file_is_the_repo_root_env_regardless_of_cwd(monkeypatch, tmp_path):
    # The documented local-dev workflow runs the backend from `backend/`, not the
    # repo root, so the configured .env path must not depend on process cwd.
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file"] == Path(__file__).resolve().parent.parent.parent / ".env"
