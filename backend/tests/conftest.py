import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401 - registers tables on SQLModel.metadata
from app.config import settings
from app.db import get_engine, get_session
from app.main import app
from app.models.company import Company
from app.models.membership import Membership
from app.models.user import User
from app.services.auth import create_access_token, decode_access_token, hash_password


@pytest.fixture(autouse=True)
def _no_real_services(monkeypatch):
    """A developer's .env may point at the real S3 bucket or Qdrant server; tests
    must never touch either."""
    monkeypatch.setattr(settings, "s3_bucket", "")
    monkeypatch.setattr(settings, "qdrant_url", "")


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


def slug_of(company_name: str) -> str:
    return company_name.lower().replace(" ", "-")


def _add_member(
    db_engine,
    email: str,
    company_name: str = "Test Company",
    role: str = "member",
    department_id: uuid.UUID | None = None,
    company_status: str = "active",
) -> uuid.UUID:
    """Get-or-create the company, the account and its membership; returns the user id."""
    with Session(db_engine) as session:
        company = session.exec(select(Company).where(Company.name == company_name)).first()
        if not company:
            company = Company(name=company_name, slug=slug_of(company_name), status=company_status)
            session.add(company)
            session.commit()
            session.refresh(company)

        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            user = User(email=email, password_hash=hash_password("password123"))
            session.add(user)
            session.commit()
            session.refresh(user)

        membership = session.exec(
            select(Membership).where(Membership.user_id == user.id, Membership.company_id == company.id)
        ).first()
        if not membership:
            session.add(
                Membership(user_id=user.id, company_id=company.id, role=role, department_id=department_id)
            )
            session.commit()
        return user.id


def company_id_of(db_engine, company_name: str = "Test Company") -> uuid.UUID:
    with Session(db_engine) as session:
        return session.exec(select(Company.id).where(Company.name == company_name)).one()


def client_for(user_id: uuid.UUID, company_slug: str | None = None) -> TestClient:
    """A signed-in client. With company_slug, every path is relative to that company:
    client.get("/documents") requests /companies/<slug>/documents. Without it, paths
    are absolute (account-level and platform routes)."""
    base_url = "http://testserver" + (f"/companies/{company_slug}" if company_slug else "")
    test_client = TestClient(app, base_url=base_url)
    test_client.headers["Authorization"] = f"Bearer {create_access_token(user_id)}"
    return test_client


def account(test_client: TestClient) -> TestClient:
    """The same user, outside any company: for /auth, /companies, /invites, /instance."""
    return client_for(_user_id_from(test_client))


def _registered_client(
    db_engine,
    email: str,
    company_name: str = "Test Company",
    role: str = "member",
    department_id: uuid.UUID | None = None,
) -> TestClient:
    """A client for a member of the company, scoped to it (see client_for)."""
    _override_db(db_engine)
    user_id = _add_member(db_engine, email, company_name, role, department_id)
    return client_for(user_id, slug_of(company_name))


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
def member_client(client):
    return client


@pytest.fixture
def admin_client(db_engine):
    test_client = _registered_client(db_engine, "admin-user@example.com", role="admin")
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)


@pytest.fixture
def owner_client(db_engine):
    test_client = _registered_client(db_engine, "owner-user@example.com", role="owner")
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)


@pytest.fixture
def instance_admin_client(db_engine):
    """An instance admin with no memberships. Paths are absolute."""
    _override_db(db_engine)
    with Session(db_engine) as session:
        user = User(
            email="instance-admin@example.com",
            password_hash=hash_password("password123"),
            is_instance_admin=True,
        )
        session.add(user)
        session.commit()
        user_id = user.id

    try:
        yield client_for(user_id)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)


@pytest.fixture
def other_client(client, db_engine) -> TestClient:
    return _registered_client(db_engine, "other-user@example.com")


@pytest.fixture
def other_company_client(db_engine) -> TestClient:
    test_client = _registered_client(
        db_engine, "other-company-user@example.com", company_name="Other Company"
    )
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_engine, None)


def _user_id_from(test_client: TestClient) -> uuid.UUID:
    token = test_client.headers["Authorization"].removeprefix("Bearer ")
    return decode_access_token(token)


@pytest.fixture
def test_user_id(client) -> uuid.UUID:
    return _user_id_from(client)


@pytest.fixture
def other_user_id(other_client) -> uuid.UUID:
    return _user_id_from(other_client)
