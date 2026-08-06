from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, create_engine
from sqlalchemy.pool import StaticPool

from app.db import run_migrations


def test_run_migrations_executes_successfully(tmp_path):
    db_path = tmp_path / "test_run_migrations.db"
    db_url = f"sqlite:///{db_path}"
    run_migrations(target_url=db_url)


def test_alembic_upgrade_and_downgrade(tmp_path):
    db_path = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_path}"

    base_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = base_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "users" in tables
    assert "documents" in tables
    assert "conversations" in tables
    assert "messages" in tables

    # 2. Downgrade by step (-1)
    command.downgrade(alembic_cfg, "-1")

    # 3. Downgrade to base (all tables dropped)
    command.downgrade(alembic_cfg, "base")
    inspector = inspect(engine)
    tables_after_rollback = [t for t in inspector.get_table_names() if t != "alembic_version"]
    assert len(tables_after_rollback) == 0
