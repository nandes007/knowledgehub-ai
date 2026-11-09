import uuid
from pathlib import Path

import pytest
from sqlmodel import Session

from app.models.company import Company
from app.models.department import Department
from app.models.document import Document
from app.models.user import User
from app.services.auth import hash_password
from ingestion.index import VectorStore
from ingestion.pipeline import ingest_document, ingest_file


class _FakeLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class _FailingLLM:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding API is down")


def test_ingest_file_raises_a_clear_error_when_extracted_text_is_near_empty(tmp_path):
    file_path = tmp_path / "scanned.md"
    file_path.write_text("   \n\n  \n")
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))

    with pytest.raises(ValueError, match="no readable text"):
        ingest_file(
            file_path,
            document_id="doc-1",
            company_id="comp-1",
            user_id="u1",
            filename="scanned.md",
            llm=_FakeLLM(),
            vector_store=store,
        )


def test_ingest_file_converts_chunks_embeds_and_upserts(tmp_path):
    file_path = tmp_path / "policy.md"
    file_path.write_text("# Policy\n\nEmployees get 20 days of PTO per year.")
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))

    chunk_count = ingest_file(
        file_path,
        document_id="doc-1",
        company_id="comp-1",
        department_id="dept-1",
        user_id="u1",
        filename="policy.md",
        llm=_FakeLLM(),
        vector_store=store,
    )

    assert chunk_count >= 1
    results = store.query([1.0, 0.0], top_k=5)
    assert any("PTO" in r["text"] for r in results)
    assert results[0]["document_id"] == "doc-1"
    assert results[0]["company_id"] == "comp-1"
    assert results[0]["department_id"] == "dept-1"


def _make_document(
    session: Session,
    tmp_path,
    *,
    content: str = "# Policy\n\nEmployees get 20 days of PTO.",
    department_id: uuid.UUID | None = None,
) -> Document:
    company = Company(name=f"Company {uuid.uuid4().hex[:6]}", status="active")
    session.add(company)
    session.commit()

    user = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("pw"),
        role="admin",
        approval_status="approved",
        company_id=company.id,
    )
    session.add(user)
    session.commit()

    file_path = tmp_path / "policy.md"
    file_path.write_text(content)
    document = Document(
        company_id=company.id,
        uploaded_by=user.id,
        filename="policy.md",
        content_type="text/markdown",
        file_path=str(file_path),
        file_hash="irrelevant",
        department_id=department_id,
        status="processing",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def test_ingest_document_marks_ready_with_chunk_count_and_metadata(db_engine, tmp_path):
    with Session(db_engine, expire_on_commit=False) as session:
        dept = Department(name="Engineering", company_id=uuid.uuid4())
        # create valid company for dept
        company = Company(name="Eng Co", status="active")
        session.add(company)
        session.commit()
        dept.company_id = company.id
        session.add(dept)
        session.commit()

        document = _make_document(session, tmp_path, department_id=dept.id)
        document_id = document.id
        comp_id = str(document.company_id)
        dept_id = str(dept.id)

    store = VectorStore(persist_dir=str(tmp_path / "chroma"))

    ingest_document(document_id, engine=db_engine, llm=_FakeLLM(), vector_store=store)

    with Session(db_engine) as session:
        updated = session.get(Document, document_id)

    assert updated.status == "ready"
    assert updated.progress == 100
    assert updated.chunk_count is not None
    assert updated.chunk_count >= 1
    assert updated.error_message is None

    chunks = store.query([1.0, 0.0], top_k=5)
    assert len(chunks) >= 1
    assert chunks[0]["document_id"] == str(document_id)
    assert chunks[0]["company_id"] == comp_id
    assert chunks[0]["department_id"] == dept_id


def test_ingest_document_marks_failed_with_error_message_on_failure(db_engine, tmp_path):
    with Session(db_engine) as session:
        document = _make_document(session, tmp_path)
        document_id = document.id

    store = VectorStore(persist_dir=str(tmp_path / "chroma"))

    ingest_document(document_id, engine=db_engine, llm=_FailingLLM(), vector_store=store)

    with Session(db_engine) as session:
        updated = session.get(Document, document_id)

    assert updated.status == "failed"
    assert updated.chunk_count is None
    assert "embedding API is down" in updated.error_message


def test_ingest_document_is_a_noop_for_an_unknown_document_id(db_engine, tmp_path):
    store = VectorStore(persist_dir=str(tmp_path / "chroma"))

    # Should not raise even though no document row exists for this id.
    ingest_document(uuid.uuid4(), engine=db_engine, llm=_FakeLLM(), vector_store=store)


def test_reindex_rebuilds_an_empty_store_from_stored_files(db_engine, tmp_path):
    from app.cli import reindex

    with Session(db_engine, expire_on_commit=False) as session:
        document_id = _make_document(session, tmp_path).id
    store = VectorStore(persist_dir=str(tmp_path / "qdrant"))

    assert reindex(db_engine, llm=_FakeLLM(), vector_store=store) == (1, 1)
    chunks = store.query([1.0, 0.0], top_k=50)
    assert chunks and all(c["document_id"] == str(document_id) for c in chunks)

    # Re-running overwrites rather than duplicates.
    reindex(db_engine, llm=_FakeLLM(), vector_store=store)
    assert len(store.query([1.0, 0.0], top_k=50)) == len(chunks)


def test_ingest_document_stores_pictures_and_reingest_replaces_them(db_engine, tmp_path, monkeypatch):
    import io

    from PIL import Image

    from app.config import settings
    from app.services import storage

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    image_path = tmp_path / "diagram.png"
    Image.new("RGB", (400, 300), "white").save(image_path)

    class _VisionLLM(_FakeLLM):
        def transcribe_image(self, png: bytes) -> str:
            return "Deployment flow: build, test, deploy."

    with Session(db_engine, expire_on_commit=False) as session:
        document = _make_document(session, tmp_path)
        document.file_path = str(image_path)
        document.images = [{"uri": storage.save(f"document-images/{document.id}/7.png", b"old"), "page": None, "caption": "old"}]
        session.add(document)
        session.commit()
        old_uri = document.images[0]["uri"]
    store = VectorStore(persist_dir=str(tmp_path / "qdrant"))

    for _ in range(2):  # the second run is a reindex: replaces, never duplicates
        ingest_document(document.id, engine=db_engine, llm=_VisionLLM(), vector_store=store)

    with Session(db_engine) as session:
        stored = session.get(Document, document.id)
        assert stored.status == "ready"
        assert len(stored.images) == 1 and stored.images[0]["caption"].startswith("Deployment flow")
        assert Image.open(io.BytesIO(storage.read(stored.images[0]["uri"]))).size == (400, 300)
    assert not Path(old_uri).exists()  # the stale picture from the earlier run is gone
    assert len(store.query([1.0, 0.0], top_k=50)) == 1
