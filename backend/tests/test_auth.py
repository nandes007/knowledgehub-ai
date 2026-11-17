import uuid

from sqlmodel import Session, select

from app.config import settings
from app.main import app
from app.models.company import Company
from app.models.department import Department
from app.models.document import Document
from app.models.membership import Membership
from app.models.user import User
from app.services.auth import verify_password
from app.services.llm import get_llm_provider
from ingestion.index import VectorStore, get_vector_store
from tests.conftest import _add_member, _registered_client, _user_id_from, account, client_for


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


def _register(anon_client, email: str = "new@example.com", **extra):
    return anon_client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "display_name": "New User", **extra},
    )


def _login(anon_client, email: str = "new@example.com", password: str = "password123"):
    return anon_client.post("/auth/login", json={"email": email, "password": password})


# --- Signup modes ----------------------------------------------------------------------------


def test_open_signup_creates_only_an_account_that_can_log_in_at_once(anon_client, db_engine):
    response = _register(anon_client)

    assert response.status_code == 201
    assert response.json() == {"message": "Account created", "approval_status": "approved", "company_slug": None}
    with Session(db_engine) as session:
        user = session.exec(select(User).where(User.email == "new@example.com")).one()
        assert user.display_name == "New User"
        assert user.is_instance_admin is False
        assert verify_password("password123", user.password_hash)
        assert session.exec(select(Company)).all() == []
        assert session.exec(select(Membership)).all() == []

    token = _login(anon_client).json()["access_token"]
    me = anon_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == "new@example.com"
    assert me["companies"] == []


def test_approval_signup_waits_for_an_instance_admin(anon_client, instance_admin_client, monkeypatch):
    monkeypatch.setattr(settings, "signup_mode", "approval")

    response = _register(anon_client)
    assert response.status_code == 201
    assert response.json()["approval_status"] == "pending"

    pending = _login(anon_client)
    assert pending.status_code == 403
    assert pending.json()["detail"] == "Your account is pending approval"

    user_id = instance_admin_client.get("/instance/users", params={"approval_status": "pending"}).json()[0]["id"]
    assert instance_admin_client.patch(f"/instance/users/{user_id}/approve").status_code == 200
    assert _login(anon_client).status_code == 200

    assert instance_admin_client.patch(f"/instance/users/{user_id}/reject").status_code == 200
    rejected = _login(anon_client)
    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "Your registration has been rejected"


def test_a_token_stops_working_once_the_account_is_rejected(client, db_engine, test_user_id):
    with Session(db_engine) as session:
        user = session.get(User, test_user_id)
        user.approval_status = "rejected"
        session.add(user)
        session.commit()

    assert account(client).get("/auth/me").status_code == 403


def test_closed_signup_refuses_registration_without_an_invite(anon_client, db_engine, monkeypatch):
    monkeypatch.setattr(settings, "signup_mode", "closed")

    response = _register(anon_client)

    assert response.status_code == 403
    assert "invite" in response.json()["detail"]
    with Session(db_engine) as session:
        assert session.exec(select(User)).all() == []


def test_register_rejects_duplicate_email(anon_client):
    _register(anon_client)

    response = _register(anon_client)

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_email_matching_ignores_case(anon_client):
    # Invites bind to a lowercased email, so one person must not get two accounts by casing.
    _register(anon_client, email="Bob@Example.com")

    assert _register(anon_client, email="bob@example.com").status_code == 409
    assert _login(anon_client, email="BOB@example.com").status_code == 200


def test_register_rejects_a_short_password(anon_client):
    response = anon_client.post("/auth/register", json={"email": "a@example.com", "password": "short"})
    assert response.status_code == 422


# --- Login -----------------------------------------------------------------------------------


def test_login_rejects_wrong_password(anon_client):
    _register(anon_client)

    response = _login(anon_client, password="wrong-password")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_rejects_unknown_email(anon_client):
    response = _login(anon_client, email="nobody@example.com")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_still_works_when_one_of_the_users_companies_is_suspended(client, db_engine):
    """Suspension blocks the company, not the account."""
    _add_member(db_engine, "test-user@example.com", company_name="Second Company", role="owner")
    with Session(db_engine) as session:
        company = session.exec(select(Company).where(Company.name == "Test Company")).one()
        company.status = "suspended"
        session.add(company)
        session.commit()

    suspended = client.get("/documents")
    assert suspended.status_code == 403
    assert suspended.json()["detail"] == "This company has been suspended"

    me = account(client).get("/auth/me")
    assert me.status_code == 200
    assert client_for(_user_id_from(client), "second-company").get("/documents").status_code == 200


# --- /auth/me --------------------------------------------------------------------------------


def test_me_lists_every_company_with_the_role_and_department_held_there(client, db_engine, test_user_id):
    with Session(db_engine) as session:
        company = session.exec(select(Company).where(Company.name == "Test Company")).one()
        dept = Department(name="Engineering", company_id=company.id)
        session.add(dept)
        session.commit()
        membership = session.exec(select(Membership).where(Membership.user_id == test_user_id)).one()
        membership.department_id = dept.id
        session.add(membership)
        session.commit()
        dept_id, company_id = str(dept.id), str(company.id)
    _add_member(db_engine, "test-user@example.com", company_name="Another Co", role="owner")

    response = account(client).get("/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "test-user@example.com"
    assert body["is_instance_admin"] is False
    assert body["approval_status"] == "approved"
    assert body["companies"] == [
        {
            "id": body["companies"][0]["id"],
            "name": "Another Co",
            "slug": "another-co",
            "status": "active",
            "role": "owner",
            "department_id": None,
            "department_name": None,
        },
        {
            "id": company_id,
            "name": "Test Company",
            "slug": "test-company",
            "status": "active",
            "role": "member",
            "department_id": dept_id,
            "department_name": "Engineering",
        },
    ]


# --- Authentication is required everywhere ---------------------------------------------------


def test_me_without_a_token_returns_401(anon_client):
    response = anon_client.get("/auth/me")

    assert response.status_code == 401


def test_protected_route_without_a_token_returns_401(anon_client):
    response = anon_client.get("/companies/test-company/conversations")

    assert response.status_code == 401


def test_chat_without_a_token_returns_401(anon_client):
    response = anon_client.post("/companies/test-company/chat", data={"message": "hi"})

    assert response.status_code == 401


def test_documents_without_a_token_returns_401(anon_client):
    response = anon_client.get("/companies/test-company/documents")

    assert response.status_code == 401


def test_protected_route_with_a_garbage_token_returns_401(anon_client):
    anon_client.headers["Authorization"] = "Bearer not-a-real-token"

    response = anon_client.get("/companies/test-company/conversations")

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
