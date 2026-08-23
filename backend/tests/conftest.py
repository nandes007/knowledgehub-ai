import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401 - registers tables on SQLModel.metadata
from app.db import get_engine, get_session
from app.main import app
from app.models.company import Company
from app.models.user import User
from app.services.auth import create_access_token, decode_access_token, hash_password


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


def _registered_client(
    db_engine, email: str, company_name: str = "Test Company", role: str = "member"
) -> TestClient:
    _override_db(db_engine)
    with Session(db_engine) as session:
        company = session.exec(select(Company).where(Company.name == company_name)).first()
        if not company:
            company = Company(name=company_name, status="active")
            session.add(company)
            session.commit()
            session.refresh(company)

        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            user = User(
                email=email,
                password_hash=hash_password("password123"),
                company_id=company.id,
                role=role,
                approval_status="approved",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        user_id = user.id

    test_client = TestClient(app)
    test_client.headers["Authorization"] = f"Bearer {create_access_token(user_id)}"
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
def admin_client(db_engine):
    test_client = _registered_client(db_engine, "admin-user@example.com", role="admin")
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
