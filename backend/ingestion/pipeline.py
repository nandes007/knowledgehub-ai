import logging
import re
import uuid
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session

from app.models.document import Document
from app.services import storage
from app.services.llm import LLMProvider, get_llm_provider
from ingestion.chunk import chunk_markdown
from ingestion.convert import convert_to_markdown
from ingestion.index import VectorStore, get_vector_store
from ingestion.ocr import (
    IMAGE_EXTENSIONS,
    IMAGE_MARKER,
    ExtractedImage,
    image_to_markdown,
    office_to_markdown,
    pdf_to_markdown,
)

_logger = logging.getLogger("app.ingestion")

_MIN_EXTRACTED_CHARS = 20
_CAPTION_LENGTH = 300


def extract_markdown(file_path: Path, llm: LLMProvider, images: list[ExtractedImage] | None = None) -> str:
    """Any supported file to markdown, OCR included. Pass `images` to collect the pictures
    worth showing in answers; their positions are left in the text as markers."""
    suffix = file_path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return image_to_markdown(file_path, llm, images)
    if suffix == ".pdf":
        return pdf_to_markdown(file_path, llm, images)
    if suffix in (".docx", ".pptx"):
        return office_to_markdown(file_path, llm, images)
    return convert_to_markdown(file_path)


def _attach_images(chunks: list, images: list[ExtractedImage]) -> None:
    for chunk in chunks:
        indices = dict.fromkeys(int(n) for n in IMAGE_MARKER.findall(chunk.text))
        chunk.images = [{"index": n, "caption": images[n].caption[:_CAPTION_LENGTH]} for n in indices]
        chunk.text = re.sub(r"\n{3,}", "\n\n", IMAGE_MARKER.sub("", chunk.text)).strip()


def ingest_file(
    file_path: Path,
    *,
    document_id: str,
    user_id: str,
    filename: str,
    doc_type: str = "general",
    company_id: str | None = None,
    department_id: str | None = None,
    department: str | None = None,
    visibility: str = "company",
    llm: LLMProvider | None = None,
    vector_store: VectorStore | None = None,
    chunk_size: int | None = None,
    images: list[ExtractedImage] | None = None,
) -> int:
    """Pass an empty `images` list to receive the document's pictures; chunks reference
    them by index."""
    llm = llm or get_llm_provider()
    vector_store = vector_store or get_vector_store()

    collected: list[ExtractedImage] = [] if images is None else images
    text = extract_markdown(file_path, llm, collected)
    if len(IMAGE_MARKER.sub("", text).strip()) < _MIN_EXTRACTED_CHARS:
        raise ValueError("This file has no readable text.")
    # chunk_size is an override for the eval harness; production uses the default.
    chunks = chunk_markdown(text, **({"chunk_size": chunk_size} if chunk_size else {}))
    _attach_images(chunks, collected)
    embeddings = llm.embed_texts([c.text for c in chunks])
    # Re-ingest replaces the document's chunks: drop the old ones only once embedding
    # succeeded, so a failed re-run leaves the document searchable.
    vector_store.delete_by_document(document_id)

    return vector_store.upsert_chunks(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
        chunks=chunks,
        embeddings=embeddings,
        doc_type=doc_type,
        company_id=company_id,
        department_id=department_id,
        department=department,
        visibility=visibility,
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

        images: list[ExtractedImage] = []
        try:
            with storage.local_copy(document.file_path) as file_path:
                chunk_count = ingest_file(
                    file_path,
                    document_id=str(document.id),
                    user_id=str(document.user_id),
                    filename=document.filename,
                    doc_type=document.doc_type,
                    company_id=str(document.company_id),
                    department_id=str(document.department_id) if document.department_id else None,
                    department=document.department,
                    visibility=document.visibility,
                    llm=llm,
                    vector_store=vector_store,
                    images=images,
                )
            stored = _store_images(document, images)
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(exc)
            session.add(document)
            session.commit()
            return

        stale = [img["uri"] for img in document.images or [] if img["uri"] not in {i["uri"] for i in stored}]
        document.status = "ready"
        document.chunk_count = chunk_count
        document.images = stored
        session.add(document)
        session.commit()
        delete_files(stale)


def _store_images(document: Document, images: list[ExtractedImage]) -> list[dict]:
    # Deterministic names: re-ingesting overwrites rather than piling up copies.
    return [
        {
            "uri": storage.save(f"document-images/{document.id}/{n}.png", image.png),
            "page": image.page,
            "caption": image.caption[:_CAPTION_LENGTH],
        }
        for n, image in enumerate(images)
    ]


def delete_files(locations: list[str]) -> None:
    """Best-effort: a leftover object in storage is not worth failing a request over."""
    for location in locations:
        try:
            storage.delete(location)
        except Exception:
            _logger.exception("storage_delete_failed", extra={"location": location})
