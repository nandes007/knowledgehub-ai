import uuid

from sqlmodel import Session, select

from app.config import settings
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.services.auth import verify_password
from app.services.llm import get_llm_provider
from ingestion.index import VectorStore, get_vector_store


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


def test_register_creates_a_user_and_returns_a_token(anon_client):
    response = anon_client.post(
        "/auth/register",
        json={"email": "new-user@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_register_hashes_the_password(anon_client, db_engine):
    anon_client.post(
        "/auth/register",
        json={"email": "new-user@example.com", "password": "password123"},
    )

    with Session(db_engine) as session:
        user = session.exec(select(User).where(User.email == "new-user@example.com")).one()

    assert user.password_hash != "password123"
    assert verify_password("password123", user.password_hash)


def test_register_rejects_a_duplicate_email(anon_client):
    anon_client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "password123"},
    )

    response = anon_client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "a-different-password"},
    )

    assert response.status_code == 409


def test_login_returns_a_token_for_correct_credentials(anon_client):
    anon_client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )

    response = anon_client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_rejects_the_wrong_password(anon_client):
    anon_client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )

    response = anon_client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_rejects_an_unknown_email(anon_client):
    response = anon_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )

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


def test_user_cannot_list_another_users_documents(client, other_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        client.post("/documents", files={"file": ("mine.md", b"# Mine", "text/markdown")})
        response = other_client.get("/documents")
    finally:
        _clear_overrides()

    assert response.json() == []


def test_user_cannot_delete_another_users_document(client, other_client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        upload = client.post("/documents", files={"file": ("mine.md", b"# Mine", "text/markdown")})
        document_id = upload.json()["id"]
        response = other_client.delete(f"/documents/{document_id}")
    finally:
        _clear_overrides()

    assert response.status_code == 404
    with Session(db_engine) as session:
        assert session.get(Document, uuid.UUID(document_id)) is not None


def test_user_cannot_read_another_users_conversation_messages(client, other_client):
    conversation = client.post("/conversations").json()

    response = other_client.get(f"/conversations/{conversation['id']}/messages")

    assert response.status_code == 404
