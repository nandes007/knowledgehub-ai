import uuid

import pytest
from sqlmodel import Session

from app.models.document import Document
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
        user_id="u1",
        filename="policy.md",
        llm=_FakeLLM(),
        vector_store=store,
    )

    assert chunk_count >= 1
    results = store.query([1.0, 0.0], top_k=5)
    assert any("PTO" in r["text"] for r in results)
    assert results[0]["document_id"] == "doc-1"


def _make_document(session: Session, tmp_path, *, content: str = "# Policy\n\nEmployees get 20 days of PTO.") -> Document:
    file_path = tmp_path / "policy.md"
    file_path.write_text(content)
    document = Document(
        user_id=uuid.uuid4(),
        filename="policy.md",
        content_type="text/markdown",
        file_path=str(file_path),
        file_hash="irrelevant",
        status="processing",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def test_ingest_document_marks_ready_with_chunk_count(db_engine, tmp_path):
    with Session(db_engine) as session:
        document = _make_document(session, tmp_path)
        document_id = document.id

    store = VectorStore(persist_dir=str(tmp_path / "chroma"))

    ingest_document(document_id, engine=db_engine, llm=_FakeLLM(), vector_store=store)

    with Session(db_engine) as session:
        updated = session.get(Document, document_id)

    assert updated.status == "ready"
    assert updated.chunk_count is not None
    assert updated.chunk_count >= 1
    assert updated.error_message is None


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
