from datetime import datetime, timezone
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
import sqlalchemy as sa
from sqlalchemy import inspect, create_engine

from app.db import run_migrations


def test_run_migrations_executes_successfully(tmp_path):
    db_path = tmp_path / "test_run_migrations.db"
    db_url = f"sqlite:///{db_path}"
    run_migrations(target_url=db_url)

    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "companies" in tables
    assert "departments" in tables
    assert "users" in tables
    assert "documents" in tables
    assert "conversations" in tables
    assert "messages" in tables


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
    assert "companies" in tables
    assert "departments" in tables
    assert "users" in tables
    assert "documents" in tables
    assert "conversations" in tables
    assert "messages" in tables

    # 2. Downgrade by step (-1) to 0001
    command.downgrade(alembic_cfg, "-1")
    inspector = inspect(engine)
    tables_after_step = inspector.get_table_names()
    assert "companies" not in tables_after_step
    assert "departments" not in tables_after_step
    assert "users" in tables_after_step

    # 3. Downgrade to base (all tables dropped)
    command.downgrade(alembic_cfg, "base")
    inspector = inspect(engine)
    tables_after_rollback = [t for t in inspector.get_table_names() if t != "alembic_version"]
    assert len(tables_after_rollback) == 0


def test_migration_backfills_existing_data(tmp_path):
    db_path = tmp_path / "test_backfill.db"
    db_url = f"sqlite:///{db_path}"

    base_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = base_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

    # 1. Upgrade to initial schema (0001)
    command.upgrade(alembic_cfg, "0001_initial_schema")

    engine = create_engine(db_url)
    now = datetime.now(timezone.utc)
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    users_t = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("email", sa.String()),
        sa.column("password_hash", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("role", sa.String()),
        sa.column("department", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    documents_t = sa.table(
        "documents",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("filename", sa.String()),
        sa.column("content_type", sa.String()),
        sa.column("file_path", sa.String()),
        sa.column("file_hash", sa.String()),
        sa.column("status", sa.String()),
        sa.column("doc_type", sa.String()),
        sa.column("department", sa.String()),
        sa.column("visibility", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    conversations_t = sa.table(
        "conversations",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("title", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    with engine.begin() as conn:
        conn.execute(
            sa.insert(users_t).values(
                id=user_id,
                email="legacy@example.com",
                password_hash="legacyhash",
                display_name="Legacy User",
                role="member",
                department="Engineering",
                created_at=now,
            )
        )
        conn.execute(
            sa.insert(documents_t).values(
                id=doc_id,
                user_id=user_id,
                filename="legacy.pdf",
                content_type="application/pdf",
                file_path="/uploads/legacy.pdf",
                file_hash="hash123",
                status="ready",
                doc_type="general",
                department="Engineering",
                visibility="company",
                created_at=now,
                updated_at=now,
            )
        )
        conn.execute(
            sa.insert(conversations_t).values(
                id=conv_id,
                user_id=user_id,
                title="Legacy chat",
                created_at=now,
                updated_at=now,
            )
        )

    # 2. Upgrade to head (0002)
    command.upgrade(alembic_cfg, "head")

    # 3. Verify backfill results
    with engine.connect() as conn:
        companies = conn.execute(sa.text("SELECT id, name, status FROM companies")).mappings().fetchall()
        assert len(companies) == 1
        default_company = companies[0]
        assert default_company["name"] == "Nandes Tech"
        assert default_company["status"] == "active"
        company_id = default_company["id"]

        users = conn.execute(sa.text("SELECT * FROM users")).mappings().fetchall()
        assert len(users) == 1
        user = users[0]
        assert str(user["id"]).replace("-", "") == str(user_id).replace("-", "")
        assert str(user["company_id"]).replace("-", "") == str(company_id).replace("-", "")
        assert user["role"] == "admin"
        assert user["approval_status"] == "approved"

        docs = conn.execute(sa.text("SELECT * FROM documents")).mappings().fetchall()
        assert len(docs) == 1
        doc = docs[0]
        assert str(doc["id"]).replace("-", "") == str(doc_id).replace("-", "")
        assert str(doc["company_id"]).replace("-", "") == str(company_id).replace("-", "")
        assert str(doc["uploaded_by"]).replace("-", "") == str(user_id).replace("-", "")

        convs = conn.execute(sa.text("SELECT * FROM conversations")).mappings().fetchall()
        assert len(convs) == 1
        conv = convs[0]
        assert str(conv["id"]).replace("-", "") == str(conv_id).replace("-", "")
        assert str(conv["company_id"]).replace("-", "") == str(company_id).replace("-", "")
        assert str(conv["user_id"]).replace("-", "") == str(user_id).replace("-", "")
