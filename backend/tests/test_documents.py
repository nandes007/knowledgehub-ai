import hashlib
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.main import app
from app.models.company import Company
from app.models.department import Department
from app.models.document import Document
from app.models.user import User
from app.services.auth import create_access_token, hash_password
from app.services.llm import get_llm_provider
from ingestion.index import VectorStore, get_vector_store
from tests.conftest import _override_db


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class _FailingLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding API is down")


def _override_llm(llm) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: llm


def _override_store(store: VectorStore) -> None:
    app.dependency_overrides[get_vector_store] = lambda: store


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_llm_provider, None)
    app.dependency_overrides.pop(get_vector_store, None)


def test_upload_document_returns_id_and_processing_status(admin_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        response = admin_client.post(
            "/documents",
            files={"file": ("policy.md", b"# Vacation Policy\n\nEmployees get 20 days.", "text/markdown")},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 202
    body = response.json()
    assert uuid.UUID(body["id"])
    assert body["filename"] == "policy.md"
    assert body["status"] == "processing"


def test_upload_document_saves_file_and_computes_hash(admin_client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    content = b"# Remote Work Policy\n\nUp to 3 days per week."
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        response = admin_client.post(
            "/documents",
            files={"file": ("remote.md", content, "text/markdown")},
        )
    finally:
        _clear_overrides()
    document_id = uuid.UUID(response.json()["id"])

    with Session(db_engine) as session:
        document = session.get(Document, document_id)

    assert document is not None
    assert document.file_hash == hashlib.sha256(content).hexdigest()
    assert document.content_type == "text/markdown"
    saved_path = Path(document.file_path)
    assert saved_path.exists()
    assert saved_path.read_bytes() == content


def test_upload_document_sets_company_and_uploaded_by(admin_client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        response = admin_client.post(
            "/documents",
            files={"file": ("a.md", b"content", "text/markdown")},
        )
    finally:
        _clear_overrides()
    document_id = uuid.UUID(response.json()["id"])

    with Session(db_engine) as session:
        document = session.get(Document, document_id)
        admin = session.exec(select(User).where(User.email == "admin-user@example.com")).first()

    assert document is not None
    assert document.uploaded_by == admin.id
    assert document.company_id == admin.company_id


def test_upload_document_rejects_files_over_the_size_limit(admin_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    oversized = b"x" * (2 * 1024 * 1024)

    _override_llm(_FakeLLM())
    try:
        response = admin_client.post(
            "/documents",
            files={"file": ("big.txt", oversized, "text/plain")},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 413
    assert list(Path(tmp_path).iterdir()) == []


def test_upload_document_rejects_unsupported_file_types(admin_client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    try:
        response = admin_client.post(
            "/documents",
            files={"file": ("virus.exe", b"MZ\x90\x00garbage", "application/octet-stream")},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 400
    assert "unsupported file type" in response.json()["detail"].lower()
    with Session(db_engine) as session:
        assert session.exec(select(Document)).first() is None
    assert not (tmp_path / "uploads").exists()


def test_upload_document_rejects_a_duplicate_within_same_company(admin_client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    content = b"# Policy\n\nEmployees get 20 days of PTO."
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        first = admin_client.post("/documents", files={"file": ("policy.md", content, "text/markdown")})
        second = admin_client.post("/documents", files={"file": ("policy-copy.md", content, "text/markdown")})
    finally:
        _clear_overrides()

    assert first.status_code == 202
    assert second.status_code == 409
    assert "already been uploaded" in second.json()["detail"].lower()
    with Session(db_engine) as session:
        assert len(list(session.exec(select(Document)))) == 1


def test_upload_document_allows_duplicate_hash_in_different_company(db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    content = b"# Shared Knowledge\n\nCommon standard across companies."
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))

    _override_db(db_engine)
    with Session(db_engine, expire_on_commit=False) as session:
        c1 = Company(name="Company Alpha", status="active")
        c2 = Company(name="Company Beta", status="active")
        session.add_all([c1, c2])
        session.commit()

        u1 = User(
            email="admin@alpha.com",
            password_hash=hash_password("pw"),
            role="admin",
            approval_status="approved",
            company_id=c1.id,
        )
        u2 = User(
            email="admin@beta.com",
            password_hash=hash_password("pw"),
            role="admin",
            approval_status="approved",
            company_id=c2.id,
        )
        session.add_all([u1, u2])
        session.commit()
        u1_id, u2_id = u1.id, u2.id

    client1 = TestClient(app)
    client1.headers["Authorization"] = f"Bearer {create_access_token(u1_id)}"
    client2 = TestClient(app)
    client2.headers["Authorization"] = f"Bearer {create_access_token(u2_id)}"

    try:
        res1 = client1.post("/documents", files={"file": ("doc.md", content, "text/markdown")})
        res2 = client2.post("/documents", files={"file": ("doc.md", content, "text/markdown")})
    finally:
        _clear_overrides()

    assert res1.status_code == 202
    assert res2.status_code == 202


def test_upload_document_rejects_member_role(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    try:
        response = client.post(
            "/documents",
            files={"file": ("policy.md", b"# Policy", "text/markdown")},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_upload_document_ingests_in_the_background_and_marks_ready(admin_client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))
    _override_llm(_FakeLLM())
    _override_store(store)
    try:
        response = admin_client.post(
            "/documents",
            files={"file": ("policy.md", b"# Policy\n\nEmployees get 20 days of PTO.", "text/markdown")},
        )
    finally:
        _clear_overrides()

    document_id = uuid.UUID(response.json()["id"])
    with Session(db_engine) as session:
        document = session.get(Document, document_id)

    assert document.status == "ready"
    assert document.chunk_count is not None and document.chunk_count >= 1
    results = store.query([1.0, 0.0], top_k=5)
    assert any(r["document_id"] == str(document_id) for r in results)


def test_upload_document_marks_failed_on_ingestion_error(admin_client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FailingLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        response = admin_client.post(
            "/documents",
            files={"file": ("policy.md", b"# Policy\n\nEmployees get 20 days of PTO.", "text/markdown")},
        )
    finally:
        _clear_overrides()

    document_id = uuid.UUID(response.json()["id"])
    with Session(db_engine) as session:
        document = session.get(Document, document_id)

    assert document.status == "failed"
    assert document.error_message == "embedding API is down"


def test_list_documents_returns_status_chunk_count_and_timestamps(admin_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        admin_client.post(
            "/documents",
            files={"file": ("vacation.md", b"# Vacation Policy\n\nEmployees get 20 days.", "text/markdown")},
        )
        response = admin_client.get("/documents")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    documents = response.json()
    assert len(documents) == 1
    doc = documents[0]
    assert doc["filename"] == "vacation.md"
    assert doc["status"] == "ready"
    assert doc["chunk_count"] == 1
    assert doc["error_message"] is None
    assert "created_at" in doc


def test_list_documents_returns_newest_first(admin_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        first = admin_client.post("/documents", files={"file": ("a.md", b"# A\n\ncontent a", "text/markdown")})
        second = admin_client.post("/documents", files={"file": ("b.md", b"# B\n\ncontent b", "text/markdown")})
        response = admin_client.get("/documents")
    finally:
        _clear_overrides()

    ids = [d["id"] for d in response.json()]
    assert ids[0] == second.json()["id"]
    assert ids[1] == first.json()["id"]


def test_delete_document_removes_file_db_row_and_vectors(admin_client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))
    _override_llm(_FakeLLM())
    _override_store(store)
    try:
        upload = admin_client.post(
            "/documents",
            files={"file": ("vacation.md", b"# Vacation Policy\n\nEmployees get 20 days.", "text/markdown")},
        )
        document_id = upload.json()["id"]
        with Session(db_engine) as session:
            saved_path = Path(session.get(Document, uuid.UUID(document_id)).file_path)
        assert saved_path.exists()

        response = admin_client.delete(f"/documents/{document_id}")
    finally:
        _clear_overrides()

    assert response.status_code == 204
    assert not saved_path.exists()
    with Session(db_engine) as session:
        assert session.get(Document, uuid.UUID(document_id)) is None
    results = store.query([1.0, 0.0], top_k=10)
    assert all(r["document_id"] != document_id for r in results)


def test_delete_document_rejects_member_role(client):
    response = client.delete(f"/documents/{uuid.uuid4()}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_delete_cross_company_document_returns_404(db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))

    _override_db(db_engine)
    with Session(db_engine, expire_on_commit=False) as session:
        c1 = Company(name="Company 1", status="active")
        c2 = Company(name="Company 2", status="active")
        session.add_all([c1, c2])
        session.commit()

        u1 = User(
            email="admin1@c1.com",
            password_hash=hash_password("pw"),
            role="admin",
            approval_status="approved",
            company_id=c1.id,
        )
        u2 = User(
            email="admin2@c2.com",
            password_hash=hash_password("pw"),
            role="admin",
            approval_status="approved",
            company_id=c2.id,
        )
        session.add_all([u1, u2])
        session.commit()
        u1_id, u2_id = u1.id, u2.id

    client1 = TestClient(app)
    client1.headers["Authorization"] = f"Bearer {create_access_token(u1_id)}"
    client2 = TestClient(app)
    client2.headers["Authorization"] = f"Bearer {create_access_token(u2_id)}"

    try:
        upload = client1.post("/documents", files={"file": ("secret.md", b"secret", "text/markdown")})
        doc_id = upload.json()["id"]

        # Admin 2 in Company 2 tries to delete Company 1's doc
        del_res = client2.delete(f"/documents/{doc_id}")
        assert del_res.status_code == 404
    finally:
        _clear_overrides()
