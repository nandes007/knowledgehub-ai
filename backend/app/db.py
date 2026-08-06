from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from app.config import settings

engine = create_engine(settings.database_url)


def run_migrations(target_url: str | None = None) -> None:
    base_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = base_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))
    url = target_url or settings.database_url
    safe_url = url.replace("%", "%%")
    alembic_cfg.set_main_option("sqlalchemy.url", safe_url)
    command.upgrade(alembic_cfg, "head")


def create_db_and_tables() -> None:
    run_migrations()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def get_engine() -> Engine:
    return engine

