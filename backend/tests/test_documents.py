import hashlib
import uuid
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.main import app
from app.models.document import Document
from app.seed import SEED_USER_ID
from app.services.llm import get_llm_provider
from ingestion.index import VectorStore, get_vector_store


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


def test_upload_document_returns_id_and_processing_status(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        response = client.post(
            "/documents",
            files={"file": ("policy.md", b"# Vacation Policy\n\nEmployees get 20 days.", "text/markdown")},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 202
    body = response.json()
    assert uuid.UUID(body["id"])
    assert body["filename"] == "policy.md"
    # The response reflects the row as inserted, before background ingestion runs.
    assert body["status"] == "processing"


def test_upload_document_saves_file_and_computes_hash(client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    content = b"# Remote Work Policy\n\nUp to 3 days per week."
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        response = client.post(
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


def test_upload_document_row_is_owned_by_the_seed_user(client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        response = client.post(
            "/documents",
            files={"file": ("a.md", b"content", "text/markdown")},
        )
    finally:
        _clear_overrides()
    document_id = uuid.UUID(response.json()["id"])

    with Session(db_engine) as session:
        document = session.get(Document, document_id)

    assert document.user_id == SEED_USER_ID


def test_upload_document_rejects_files_over_the_size_limit(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    oversized = b"x" * (2 * 1024 * 1024)

    _override_llm(_FakeLLM())
    try:
        response = client.post(
            "/documents",
            files={"file": ("big.txt", oversized, "text/plain")},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 413
    assert list(Path(tmp_path).iterdir()) == []


def test_upload_document_ingests_in_the_background_and_marks_ready(client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))
    _override_llm(_FakeLLM())
    _override_store(store)
    try:
        response = client.post(
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


def test_upload_document_marks_failed_on_ingestion_error(client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FailingLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        response = client.post(
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


def test_uploading_a_second_document_does_not_touch_the_first_documents_vectors(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))
    _override_llm(_FakeLLM())
    _override_store(store)
    try:
        first = client.post(
            "/documents",
            files={"file": ("vacation.md", b"# Vacation Policy\n\nEmployees get 20 days of PTO.", "text/markdown")},
        )
        first_id = uuid.UUID(first.json()["id"])
        before = store.query([1.0, 0.0], top_k=50)
        count_before = len([r for r in before if r["document_id"] == str(first_id)])

        client.post(
            "/documents",
            files={"file": ("remote.md", b"# Remote Work Policy\n\nUp to 3 days per week.", "text/markdown")},
        )
    finally:
        _clear_overrides()

    after = store.query([1.0, 0.0], top_k=50)
    count_after = len([r for r in after if r["document_id"] == str(first_id)])
    assert count_after == count_before
    assert count_after >= 1


def test_list_documents_returns_status_chunk_count_and_timestamps(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        client.post(
            "/documents",
            files={"file": ("vacation.md", b"# Vacation Policy\n\nEmployees get 20 days.", "text/markdown")},
        )
        response = client.get("/documents")
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


def test_list_documents_returns_newest_first(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    _override_llm(_FakeLLM())
    _override_store(VectorStore(persist_dir=str(tmp_path / "chroma")))
    try:
        first = client.post("/documents", files={"file": ("a.md", b"# A\n\ncontent a", "text/markdown")})
        second = client.post("/documents", files={"file": ("b.md", b"# B\n\ncontent b", "text/markdown")})
        response = client.get("/documents")
    finally:
        _clear_overrides()

    ids = [d["id"] for d in response.json()]
    assert ids[0] == second.json()["id"]
    assert ids[1] == first.json()["id"]


def test_delete_document_removes_file_db_row_and_vectors(client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))
    _override_llm(_FakeLLM())
    _override_store(store)
    try:
        upload = client.post(
            "/documents",
            files={"file": ("vacation.md", b"# Vacation Policy\n\nEmployees get 20 days.", "text/markdown")},
        )
        document_id = upload.json()["id"]
        with Session(db_engine) as session:
            saved_path = Path(session.get(Document, uuid.UUID(document_id)).file_path)
        assert saved_path.exists()

        response = client.delete(f"/documents/{document_id}")
    finally:
        _clear_overrides()

    assert response.status_code == 204
    assert not saved_path.exists()
    with Session(db_engine) as session:
        assert session.get(Document, uuid.UUID(document_id)) is None
    results = store.query([1.0, 0.0], top_k=10)
    assert all(r["document_id"] != document_id for r in results)


def test_delete_unknown_document_returns_404(client):
    response = client.delete(f"/documents/{uuid.uuid4()}")

    assert response.status_code == 404


def test_delete_document_does_not_touch_other_documents_vectors(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))
    _override_llm(_FakeLLM())
    _override_store(store)
    try:
        keep = client.post(
            "/documents",
            files={"file": ("keep.md", b"# Keep\n\ncontent to keep", "text/markdown")},
        )
        keep_id = keep.json()["id"]
        remove = client.post(
            "/documents",
            files={"file": ("remove.md", b"# Remove\n\ncontent to remove", "text/markdown")},
        )
        remove_id = remove.json()["id"]

        response = client.delete(f"/documents/{remove_id}")
    finally:
        _clear_overrides()

    assert response.status_code == 204
    results = store.query([1.0, 0.0], top_k=10)
    assert any(r["document_id"] == keep_id for r in results)
    assert all(r["document_id"] != remove_id for r in results)
