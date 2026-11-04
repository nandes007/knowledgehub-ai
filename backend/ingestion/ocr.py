"""Vision-model OCR for scanned PDFs and image uploads.

Each page is rendered to a PNG and transcribed to markdown by the vision model,
one call per page, so the result flows through the normal chunk/embed path.
"""

import io
from collections.abc import Iterator
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.llm import LLMProvider

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# PDF points are 1/72 inch, so scale 2 is ~144 dpi: body text stays legible.
_RENDER_SCALE = 2
# The vision API downsizes past 2048px anyway; shrinking first keeps payloads small.
_MAX_SIDE = 2048
# Rejected, not truncated: a silently partial document is worse than an error.
MAX_PAGES = 50


def _to_png(image: Image.Image) -> bytes:
    image = ImageOps.exif_transpose(image).convert("RGB")  # phone photos carry rotation in EXIF
    image.thumbnail((_MAX_SIDE, _MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def page_images(file_path: Path) -> Iterator[bytes]:
    """Yield one PNG per page: the image itself, or each rendered PDF page."""
    if file_path.suffix.lower() != ".pdf":
        try:
            with Image.open(file_path) as image:
                yield _to_png(image)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"Couldn't read '{file_path.name}' — the image may be corrupted.") from exc
        return

    pdf = pdfium.PdfDocument(file_path)
    try:
        if len(pdf) > MAX_PAGES:
            raise ValueError(
                f"This scanned PDF has {len(pdf)} pages; OCR supports at most {MAX_PAGES}. Split it and upload the parts."
            )
        for page in pdf:
            yield _to_png(page.render(scale=_RENDER_SCALE).to_pil())
    finally:
        pdf.close()


def ocr_to_markdown(file_path: Path, llm: LLMProvider) -> str:
    # ponytail: sequential calls, ~5s/page; run pages concurrently if big scans get slow.
    pages = (llm.transcribe_image(png) for png in page_images(file_path))
    return "\n\n".join(text.strip() for text in pages if text.strip())
