import uuid
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session

from app.models.document import Document
from app.services.llm import LLMProvider, get_llm_provider
from ingestion.chunk import chunk_markdown
from ingestion.convert import convert_to_markdown
from ingestion.index import VectorStore, get_vector_store


def ingest_file(
    file_path: Path,
    *,
    document_id: str,
    user_id: str,
    filename: str,
    doc_type: str = "general",
    department: str | None = None,
    llm: LLMProvider | None = None,
    vector_store: VectorStore | None = None,
) -> int:
    llm = llm or get_llm_provider()
    vector_store = vector_store or get_vector_store()

    text = convert_to_markdown(file_path)
    chunks = chunk_markdown(text)
    embeddings = llm.embed_texts([c.text for c in chunks])

    return vector_store.upsert_chunks(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
        chunks=chunks,
        embeddings=embeddings,
        doc_type=doc_type,
        department=department,
    )


def ingest_document(
    document_id: uuid.UUID,
    *,
    engine: Engine,
    llm: LLMProvider | None = None,
    vector_store: VectorStore | None = None,
) -> None:
    """Run the ingestion pipeline for a document row and record the outcome.

    Intended as a BackgroundTasks target: opens its own Session since the
    request-scoped one is already torn down by the time this runs.
    """
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if document is None:
            return

        try:
            chunk_count = ingest_file(
                Path(document.file_path),
                document_id=str(document.id),
                user_id=str(document.user_id),
                filename=document.filename,
                doc_type=document.doc_type,
                department=document.department,
                llm=llm,
                vector_store=vector_store,
            )
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(exc)
            session.add(document)
            session.commit()
            return

        document.status = "ready"
        document.chunk_count = chunk_count
        session.add(document)
        session.commit()
