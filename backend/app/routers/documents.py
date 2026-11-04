import hashlib
from pathlib import Path
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Engine
from sqlmodel import select

from app.config import settings
from app.db import get_engine
from app.deps import AdminDep, CurrentUserDep, SessionDep
from app.models.department import Department
from app.models.document import Document
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.document import DocumentRead, DocumentSummary
from app.services import storage
from app.services.llm import LLMProvider, get_llm_provider
from ingestion.convert import convert_to_markdown
from ingestion.index import VectorStore, get_vector_store
from ingestion.ocr import IMAGE_EXTENSIONS
from ingestion.pipeline import ingest_document

router = APIRouter()

_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md", *IMAGE_EXTENSIONS}
_VISIBILITIES = {"company", "department"}
# Served as-is for the browser to render; everything else is previewed as extracted markdown.
# Keyed on the stored extension, never the client-supplied content type.
_NATIVE_PREVIEW_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _visible_documents(user: User):
    statement = select(Document).where(Document.company_id == user.company_id)
    if user.role in ("admin", "superadmin"):
        return statement
    if user.department_id is not None:
        return statement.where(
            (Document.visibility == "company")
            | ((Document.visibility == "department") & (Document.department_id == user.department_id))
        )
    return statement.where(Document.visibility == "company")


@router.post("/documents", response_model=DocumentRead, status_code=202)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    current_user: AdminDep,
    file: UploadFile = File(...),
    department_id: uuid.UUID | None = Form(None),
    visibility: str = Form("company"),
    engine: Engine = Depends(get_engine),
    llm: LLMProvider = Depends(get_llm_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> Document:
    if current_user.company_id is None:
        raise HTTPException(status_code=400, detail="Admin must belong to a company")

    contents = await file.read()

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the upload size limit")

    extension = Path(file.filename or "").suffix.lower()
    if extension not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension or 'unknown'}'. Supported: PDF, DOCX, PPTX, MD, PNG, JPG, WEBP.",
        )

    if visibility not in _VISIBILITIES:
        raise HTTPException(status_code=400, detail=f"Visibility must be one of {sorted(_VISIBILITIES)}.")
    if visibility == "department" and not department_id:
        raise HTTPException(status_code=400, detail="A department is required for department-only visibility.")

    if department_id is not None:
        dept = session.get(Department, department_id)
        if dept is None or dept.company_id != current_user.company_id:
            raise HTTPException(status_code=404, detail="Department not found")

    file_hash = hashlib.sha256(contents).hexdigest()
    existing = session.exec(
        select(Document).where(
            Document.company_id == current_user.company_id, Document.file_hash == file_hash
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"This file has already been uploaded as '{existing.filename}'.",
        )

    document_id = uuid.uuid4()
    file_path = await run_in_threadpool(storage.save, f"{document_id}{extension}", contents)

    document = Document(
        id=document_id,
        company_id=current_user.company_id,
        uploaded_by=current_user.id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        file_path=file_path,
        file_hash=file_hash,
        status="processing",
        department_id=department_id,
        visibility=visibility,
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
    if current_user.company_id is None:
        return []

    return list(session.exec(_visible_documents(current_user).order_by(Document.created_at.desc())))


@router.get("/documents/{document_id}/preview")
def preview_document(document_id: uuid.UUID, session: SessionDep, current_user: CurrentUserDep) -> Response:
    document = None
    if current_user.company_id is not None:
        document = session.exec(_visible_documents(current_user).where(Document.id == document_id)).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    with storage.local_copy(document.file_path) as file_path:
        media_type = _NATIVE_PREVIEW_TYPES.get(file_path.suffix.lower())
        if media_type:
            return Response(file_path.read_bytes(), media_type=media_type)
        try:
            text = convert_to_markdown(file_path)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(text, media_type="text/markdown; charset=utf-8")


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    session: SessionDep,
    current_user: AdminDep,
    vector_store: VectorStore = Depends(get_vector_store),
) -> None:
    if current_user.company_id is None:
        raise HTTPException(status_code=400, detail="Admin must belong to a company")

    document = session.get(Document, document_id)
    if document is None or document.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Document not found")

    storage.delete(document.file_path)
    vector_store.delete_by_document(str(document.id))
    session.delete(document)
    session.commit()
