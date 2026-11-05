"""Files attached to chat messages: private to their conversation and never indexed.

The files and their extracted text live in storage; Message.attachments only holds
their locations.
"""

import base64
import io
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.services import storage
from app.services.llm import LLMProvider
from ingestion.ocr import to_png
from ingestion.pipeline import extract_markdown

# Keyed on the extension, never the client-supplied content type.
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".csv": "text/csv",
}
_TEXT_EXTENSIONS = {".md", ".txt", ".csv"}
MAX_FILES = 5
# ponytail: ~4 chars per token puts this near 30k tokens. Count with tiktoken if the cap
# ever needs to be exact.
MAX_TEXT_CHARS = 120_000
TRUNCATION_NOTICE = "\n\n[Truncated: this file is too long to read in full; only the first part is included.]"


def read_uploads(files: list[UploadFile]) -> list[tuple[str, str, bytes]]:
    """Validate uploads before anything is stored; returns (filename, mime, contents)."""
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Attach at most {MAX_FILES} files per message.")
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    uploads = []
    for file in files:
        name = file.filename or "file"
        extension = Path(name).suffix.lower()
        mime = IMAGE_TYPES.get(extension) or DOCUMENT_TYPES.get(extension)
        if mime is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{extension or 'unknown'}'. "
                "Supported: PNG, JPG, WEBP, GIF, PDF, DOCX, PPTX, MD, TXT, CSV.",
            )
        contents = file.file.read()
        if len(contents) > max_bytes:
            raise HTTPException(
                status_code=413, detail=f"'{name}' exceeds the {settings.max_upload_size_mb}MB limit."
            )
        if extension in IMAGE_TYPES:
            try:
                with Image.open(io.BytesIO(contents)) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError) as exc:
                raise HTTPException(status_code=400, detail=f"Couldn't read '{name}' as an image.") from exc
        uploads.append((name, mime, contents))
    return uploads


def _key(conversation_id, message_id, index: int, extension: str) -> str:
    return f"chat/{conversation_id}/{message_id}-{index}{extension}"


def save(conversation_id, message_id, uploads: list[tuple[str, str, bytes]]) -> list[dict]:
    return [
        {
            "uri": storage.save(_key(conversation_id, message_id, n, Path(name).suffix.lower()), contents),
            "filename": name,
            "mime": mime,
            "size": len(contents),
            "text_uri": None,
            "truncated": False,
        }
        for n, (name, mime, contents) in enumerate(uploads)
    ]


def is_image(attachment: dict) -> bool:
    return attachment["mime"].startswith("image/")


def needs_extraction(attachment: dict) -> bool:
    return not is_image(attachment) and attachment["text_uri"] is None


def extract(attachment: dict, llm: LLMProvider, *, conversation_id, message_id, index: int) -> dict:
    """Read a document attachment to text once and cache it next to the file, so
    follow-up turns reuse it. Returns the updated entry."""
    with storage.local_copy(attachment["uri"]) as path:
        if path.suffix.lower() in _TEXT_EXTENSIONS:
            text = path.read_text(encoding="utf-8", errors="replace")
        else:
            text = extract_markdown(path, llm)
    truncated = len(text) > MAX_TEXT_CHARS
    if truncated:
        text = text[:MAX_TEXT_CHARS] + TRUNCATION_NOTICE
    text_uri = storage.save(_key(conversation_id, message_id, index, ".extracted.md"), text.encode("utf-8"))
    return {**attachment, "text_uri": text_uri, "truncated": truncated}


def for_llm(attachment: dict) -> dict:
    """{"filename", "text"} for documents, {"filename", "image_url"} for images."""
    if is_image(attachment):
        with Image.open(io.BytesIO(storage.read(attachment["uri"]))) as image:
            png = to_png(image)  # also caps the size and flattens GIFs to their first frame
        return {"filename": attachment["filename"], "image_url": f"data:image/png;base64,{base64.b64encode(png).decode()}"}
    return {"filename": attachment["filename"], "text": storage.read(attachment["text_uri"]).decode("utf-8")}


def locations(attachment_lists: list[list[dict] | None]) -> list[str]:
    return [
        uri
        for attachments in attachment_lists
        for a in attachments or []
        for uri in (a["uri"], a.get("text_uri"))
        if uri
    ]
