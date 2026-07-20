import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import Engine
from sqlmodel import select

from app.config import settings
from app.db import get_engine
from app.deps import CurrentUserDep, SessionDep
from app.models.document import Document
from app.schemas.document import DocumentRead, DocumentSummary
from app.services.llm import LLMProvider, get_llm_provider
from ingestion.index import VectorStore, get_vector_store
from ingestion.pipeline import ingest_document

router = APIRouter()

_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md"}


@router.post("/documents", response_model=DocumentRead, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    session: SessionDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
    engine: Engine = Depends(get_engine),
    llm: LLMProvider = Depends(get_llm_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> Document:
    contents = await file.read()

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the upload size limit")

    extension = Path(file.filename or "").suffix.lower()
    if extension not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension or 'unknown'}'. Supported: PDF, DOCX, PPTX, MD.",
        )

    file_hash = hashlib.sha256(contents).hexdigest()
    existing = session.exec(
        select(Document).where(Document.user_id == current_user.id, Document.file_hash == file_hash)
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"This file has already been uploaded as '{existing.filename}'.",
        )

    document_id = uuid.uuid4()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{document_id}{Path(file.filename or '').suffix}"
    file_path.write_bytes(contents)

    document = Document(
        id=document_id,
        user_id=current_user.id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        file_path=str(file_path),
        file_hash=file_hash,
        status="processing",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    background_tasks.add_task(
        ingest_document,
        document.id,
        engine=engine,
        llm=llm,
        vector_store=vector_store,
    )

    return document


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(session: SessionDep, current_user: CurrentUserDep) -> list[Document]:
    statement = (
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    return list(session.exec(statement))


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
    vector_store: VectorStore = Depends(get_vector_store),
) -> None:
    document = session.get(Document, document_id)
    if document is None or document.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    Path(document.file_path).unlink(missing_ok=True)
    vector_store.delete_by_document(str(document.id))
    session.delete(document)
    session.commit()
