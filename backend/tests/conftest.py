import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401 - registers tables on SQLModel.metadata
from app.db import get_engine, get_session
from app.main import app
from app.services.auth import decode_access_token


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


def _override_db(db_engine) -> None:
    def _get_session_override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    app.dependency_overrides[get_engine] = lambda: db_engine


def _registered_client(db_engine, email: str) -> TestClient:
    _override_db(db_engine)
    test_client = TestClient(app)
    response = test_client.post("/auth/register", json={"email": email, "password": "password123"})
    test_client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return test_client


@pytest.fixture
def anon_client(db_engine):
    _override_db(db_engine)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)


@pytest.fixture
def client(db_engine):
    test_client = _registered_client(db_engine, "test-user@example.com")
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)


@pytest.fixture
def other_client(client, db_engine) -> TestClient:
    return _registered_client(db_engine, "other-user@example.com")


def _user_id_from(test_client: TestClient) -> uuid.UUID:
    token = test_client.headers["Authorization"].removeprefix("Bearer ")
    return decode_access_token(token)


@pytest.fixture
def test_user_id(client) -> uuid.UUID:
    return _user_id_from(client)


@pytest.fixture
def other_user_id(other_client) -> uuid.UUID:
    return _user_id_from(other_client)
