import uuid

from sqlmodel import Session, select

from app.config import settings
from app.main import app
from app.models.company import Company
from app.models.department import Department
from app.models.document import Document
from app.models.user import User
from app.services.auth import verify_password
from app.services.llm import get_llm_provider
from ingestion.index import VectorStore, get_vector_store
from tests.conftest import _registered_client


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _override_llm(llm) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: llm


def _override_store(store: VectorStore) -> None:
    app.dependency_overrides[get_vector_store] = lambda: store


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_llm_provider, None)
    app.dependency_overrides.pop(get_vector_store, None)


def test_register_creates_company_and_pending_admin_and_returns_message(anon_client, db_engine):
    response = anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "email": "admin@acme.com",
            "password": "password123",
            "display_name": "Acme Admin",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {"message": "Registration pending approval"}
    assert "access_token" not in body

    with Session(db_engine) as session:
        company = session.exec(select(Company).where(Company.name == "Acme Corp")).first()
        assert company is not None
        assert company.status == "active"

        user = session.exec(select(User).where(User.email == "admin@acme.com")).first()
        assert user is not None
        assert user.company_id == company.id
        assert user.role == "admin"
        assert user.approval_status == "pending"
        assert user.display_name == "Acme Admin"
        assert user.password_hash != "password123"
        assert verify_password("password123", user.password_hash)


def test_register_rejects_duplicate_company_name(anon_client):
    anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "email": "admin1@acme.com",
            "password": "password123",
        },
    )

    response = anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "email": "admin2@acme.com",
            "password": "password123",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Company name already taken"


def test_register_rejects_duplicate_email(anon_client):
    anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "email": "admin@example.com",
            "password": "password123",
        },
    )

    response = anon_client.post(
        "/auth/register",
        json={
            "company_name": "Beta Corp",
            "email": "admin@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_login_rejects_pending_user(anon_client):
    anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "email": "pending@example.com",
            "password": "password123",
        },
    )

    response = anon_client.post(
        "/auth/login",
        json={"email": "pending@example.com", "password": "password123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Your account is pending approval"


def test_login_rejects_rejected_user(anon_client, db_engine):
    anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "email": "rejected@example.com",
            "password": "password123",
        },
    )

    with Session(db_engine) as session:
        user = session.exec(select(User).where(User.email == "rejected@example.com")).one()
        user.approval_status = "rejected"
        session.add(user)
        session.commit()

    response = anon_client.post(
        "/auth/login",
        json={"email": "rejected@example.com", "password": "password123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Your registration has been rejected"


def test_login_rejects_user_in_suspended_company(anon_client, db_engine):
    anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "email": "suspended@example.com",
            "password": "password123",
        },
    )

    with Session(db_engine) as session:
        user = session.exec(select(User).where(User.email == "suspended@example.com")).one()
        user.approval_status = "approved"
        session.add(user)
        company = session.get(Company, user.company_id)
        company.status = "suspended"
        session.add(company)
        session.commit()

    response = anon_client.post(
        "/auth/login",
        json={"email": "suspended@example.com", "password": "password123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Your company has been suspended"


def test_login_returns_token_for_approved_user_in_active_company(anon_client, db_engine):
    anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "email": "approved@example.com",
            "password": "password123",
        },
    )

    with Session(db_engine) as session:
        user = session.exec(select(User).where(User.email == "approved@example.com")).one()
        user.approval_status = "approved"
        session.add(user)
        session.commit()

    response = anon_client.post(
        "/auth/login",
        json={"email": "approved@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["token_type"] == "bearer"


def test_login_rejects_wrong_password(anon_client, db_engine):
    anon_client.post(
        "/auth/register",
        json={
            "company_name": "Acme Corp",
            "email": "user@example.com",
            "password": "password123",
        },
    )

    with Session(db_engine) as session:
        user = session.exec(select(User).where(User.email == "user@example.com")).one()
        user.approval_status = "approved"
        session.add(user)
        session.commit()

    response = anon_client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_rejects_unknown_email(anon_client):
    response = anon_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_me_returns_tenant_and_approval_details(client, db_engine, test_user_id):
    with Session(db_engine) as session:
        user = session.get(User, test_user_id)
        company = session.get(Company, user.company_id)
        company_id = company.id
        dept = Department(company_id=company.id, name="Engineering")
        session.add(dept)
        session.commit()
        session.refresh(dept)
        dept_id = dept.id

        user.department_id = dept.id
        user.display_name = "Test User"
        session.add(user)
        session.commit()
        session.refresh(user)

    response = client.get("/auth/me")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test-user@example.com"
    assert data["display_name"] == "Test User"
    assert data["role"] == "member"
    assert data["approval_status"] == "approved"
    assert data["company_name"] == "Test Company"
    assert str(data["company_id"]) == str(company_id)
    assert data["department_name"] == "Engineering"
    assert str(data["department_id"]) == str(dept_id)


def test_me_reflects_an_admin_role(client, db_engine, test_user_id):
    with Session(db_engine) as session:
        user = session.get(User, test_user_id)
        user.role = "admin"
        session.add(user)
        session.commit()

    assert client.get("/auth/me").json()["role"] == "admin"


def test_me_without_a_token_returns_401(anon_client):
    response = anon_client.get("/auth/me")

    assert response.status_code == 401


def test_protected_route_without_a_token_returns_401(anon_client):
    response = anon_client.get("/conversations")

    assert response.status_code == 401


def test_chat_without_a_token_returns_401(anon_client):
    response = anon_client.post("/chat", json={"message": "hi"})

    assert response.status_code == 401


def test_documents_without_a_token_returns_401(anon_client):
    response = anon_client.get("/documents")

    assert response.status_code == 401


def test_protected_route_with_a_garbage_token_returns_401(anon_client):
    anon_client.headers["Authorization"] = "Bearer not-a-real-token"

    response = anon_client.get("/conversations")

    assert response.status_code == 401


def test_user_cannot_list_another_company_documents(db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))

    client_a = _registered_client(db_engine, "admin_a@comp_a.com", company_name="Company A", role="admin")
    client_b = _registered_client(db_engine, "admin_b@comp_b.com", company_name="Company B", role="admin")

    try:
        client_a.post("/documents", files={"file": ("mine.md", b"# Mine", "text/markdown")})
        response = client_b.get("/documents")
    finally:
        _clear_overrides()

    assert response.json() == []


def test_user_cannot_delete_another_company_document(db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))

    client_a = _registered_client(db_engine, "admin_a2@comp_a.com", company_name="Company A", role="admin")
    client_b = _registered_client(db_engine, "admin_b2@comp_b.com", company_name="Company B", role="admin")

    try:
        upload = client_a.post("/documents", files={"file": ("mine.md", b"# Mine", "text/markdown")})
        document_id = upload.json()["id"]
        response = client_b.delete(f"/documents/{document_id}")
    finally:
        _clear_overrides()

    assert response.status_code == 404
    with Session(db_engine) as session:
        assert session.get(Document, uuid.UUID(document_id)) is not None


def test_user_cannot_read_another_users_conversation_messages(client, other_client):
    conversation = client.post("/conversations").json()

    response = other_client.get(f"/conversations/{conversation['id']}/messages")

    assert response.status_code == 404
