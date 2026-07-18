import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401 - registers tables on SQLModel.metadata
from app.db import get_engine, get_session
from app.main import app
from app.seed import ensure_seed_user


@pytest.fixture
def db_engine():
    # StaticPool: a plain in-memory sqlite:// gives each new connection its
    # own empty DB. chat.py opens more than one Session(engine) per request,
    # so all connections in a test must share the same in-memory database.
    # Note: SQLite doesn't enforce FK constraints by default (no PRAGMA
    # foreign_keys=ON here), so these tests don't catch FK violations -
    # that's verified by the real Postgres DDL from Task 01 instead.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(db_engine):
    with Session(db_engine) as session:
        ensure_seed_user(session)

    def _get_session_override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    app.dependency_overrides[get_engine] = lambda: db_engine
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)
