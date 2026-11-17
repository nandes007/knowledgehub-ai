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
    assert "memberships" in tables
    assert "invites" in tables
    assert "documents" in tables
    assert "conversations" in tables
    assert "messages" in tables
    assert "attachments" in {c["name"] for c in inspector.get_columns("messages")}
    assert "images" in {c["name"] for c in inspector.get_columns("documents")}

    # 2. Downgrade to 0001
    command.downgrade(alembic_cfg, "0001_initial_schema")
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

    # 2. Upgrade to head
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
        assert user["approval_status"] == "approved"

        # 0005 moves the user's company and role onto a membership; the sole user owns it.
        memberships = conn.execute(sa.text("SELECT * FROM memberships")).mappings().fetchall()
        assert len(memberships) == 1
        assert str(memberships[0]["user_id"]).replace("-", "") == str(user_id).replace("-", "")
        assert str(memberships[0]["company_id"]).replace("-", "") == str(company_id).replace("-", "")
        assert memberships[0]["role"] == "owner"

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


def test_migration_moves_users_onto_memberships(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test_memberships.db'}"
    base_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(base_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(alembic_cfg, "0004_document_progress")

    engine = create_engine(db_url)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    companies_t = sa.table(
        "companies",
        *(sa.column(c, sa.Uuid() if c == "id" else sa.String()) for c in ("id", "name", "status")),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    departments_t = sa.table(
        "departments",
        sa.column("id", sa.Uuid()),
        sa.column("company_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    users_t = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("company_id", sa.Uuid()),
        sa.column("department_id", sa.Uuid()),
        sa.column("email", sa.String()),
        sa.column("password_hash", sa.String()),
        sa.column("role", sa.String()),
        sa.column("approval_status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    acme, acme_twin, globex = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    engineering = uuid.uuid4()
    # (email, company, role, department, minutes after start)
    people = [
        ("root@example.com", None, "superadmin", None, 0),
        ("early-member@acme.com", acme, "member", engineering, 1),
        ("first-admin@acme.com", acme, "admin", None, 2),
        ("second-admin@acme.com", acme, "admin", None, 3),
        ("only-member@globex.com", globex, "member", None, 4),
    ]
    with engine.begin() as conn:
        for minute, (company_id, name) in enumerate([(acme, "Acme Inc."), (acme_twin, "ACME inc"), (globex, "Login")]):
            created = start.replace(minute=minute)
            conn.execute(
                sa.insert(companies_t).values(
                    id=company_id, name=name, status="active", created_at=created, updated_at=created
                )
            )
        conn.execute(
            sa.insert(departments_t).values(
                id=engineering, company_id=acme, name="Engineering", created_at=start, updated_at=start
            )
        )
        for email, company_id, role, department_id, minute in people:
            conn.execute(
                sa.insert(users_t).values(
                    id=uuid.uuid4(),
                    company_id=company_id,
                    department_id=department_id,
                    email=email,
                    password_hash="hash",
                    role=role,
                    approval_status="approved",
                    created_at=start.replace(minute=minute),
                )
            )

    command.upgrade(alembic_cfg, "head")

    with engine.connect() as conn:
        # Slugs: from the name, deduplicated, never a path the web app uses itself.
        slugs = dict(conn.execute(sa.text("SELECT name, slug FROM companies")).fetchall())
        assert slugs == {"Acme Inc.": "acme-inc", "ACME inc": "acme-inc-2", "Login": "login-2"}

        memberships = {
            (email, slug): (role, department)
            for email, slug, role, department in conn.execute(
                sa.text(
                    "SELECT u.email, c.slug, m.role, d.name FROM memberships m "
                    "JOIN users u ON u.id = m.user_id JOIN companies c ON c.id = m.company_id "
                    "LEFT JOIN departments d ON d.id = m.department_id"
                )
            )
        }
        assert memberships == {
            ("early-member@acme.com", "acme-inc"): ("member", "Engineering"),
            ("first-admin@acme.com", "acme-inc"): ("owner", None),  # earliest admin, not earliest user
            ("second-admin@acme.com", "acme-inc"): ("admin", None),
            ("only-member@globex.com", "login-2"): ("owner", None),  # no admin: someone must own it
        }

        instance_admins = conn.execute(sa.text("SELECT email FROM users WHERE is_instance_admin")).scalars().all()
        assert instance_admins == ["root@example.com"]

    user_columns = {c["name"] for c in inspect(engine).get_columns("users")}
    assert not {"company_id", "department_id", "role"} & user_columns

    # Downgrade restores the old shape (owners fall back to admin).
    command.downgrade(alembic_cfg, "0004_document_progress")
    with engine.connect() as conn:
        roles = dict(conn.execute(sa.text("SELECT email, role FROM users")).fetchall())
    assert roles == {
        "root@example.com": "superadmin",
        "early-member@acme.com": "member",
        "first-admin@acme.com": "admin",
        "second-admin@acme.com": "admin",
        "only-member@globex.com": "admin",
    }
    assert "memberships" not in inspect(engine).get_table_names()
