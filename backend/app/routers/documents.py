import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.deps import SessionDep
from app.models.document import Document
from app.schemas.document import DocumentRead
from app.seed import SEED_USER_ID

router = APIRouter()


@router.post("/documents", response_model=DocumentRead, status_code=202)
async def upload_document(session: SessionDep, file: UploadFile = File(...)) -> Document:
    contents = await file.read()

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the upload size limit")

    document_id = uuid.uuid4()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{document_id}{Path(file.filename or '').suffix}"
    file_path.write_bytes(contents)

    document = Document(
        id=document_id,
        user_id=SEED_USER_ID,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        file_path=str(file_path),
        file_hash=hashlib.sha256(contents).hexdigest(),
        status="processing",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document
