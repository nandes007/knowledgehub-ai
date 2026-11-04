"""Vision-model OCR for scanned PDFs, PDF pages with pictures, and image uploads.

Pages that need it are rendered to PNG and transcribed to markdown by the vision
model, one call per page, so the result flows through the normal chunk/embed path.
"""

import io
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.llm import LLMProvider
from ingestion.convert import convert_to_markdown

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# PDF points are 1/72 inch, so scale 2 is ~144 dpi: body text stays legible.
_RENDER_SCALE = 2
# The vision API downsizes past 2048px anyway; shrinking first keeps payloads small.
_MAX_SIDE = 2048
# Rejected, not truncated: a silently partial document is worse than an error.
MAX_PAGES = 50
# ponytail: tuning knob. A picture covering less of the page than this is treated as
# decoration (logo, icon) and skipped; lower it if small screenshots go unread.
_MIN_PICTURE_AREA = 0.05
_MIN_TEXT_CHARS = 20


def _to_png(image: Image.Image) -> bytes:
    image = ImageOps.exif_transpose(image).convert("RGB")  # phone photos carry rotation in EXIF
    image.thumbnail((_MAX_SIDE, _MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def image_to_markdown(file_path: Path, llm: LLMProvider) -> str:
    try:
        with Image.open(file_path) as image:
            png = _to_png(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Couldn't read '{file_path.name}' — the image may be corrupted.") from exc
    return llm.transcribe_image(png).strip()


def _has_picture(page: pdfium.PdfPage) -> bool:
    width, height = page.get_size()
    for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
        left, bottom, right, top = obj.get_bounds()
        if (right - left) * (top - bottom) >= _MIN_PICTURE_AREA * width * height:
            return True
    return False


def pdf_to_markdown(file_path: Path, llm: LLMProvider) -> str:
    """Text pages are read directly; pages with pictures go to the vision model whole.

    A PDF with no text at all (a scan) is OCR'd on every page.
    """
    text = convert_to_markdown(file_path)  # also rejects corrupt PDFs with a clear error
    pdf = pdfium.PdfDocument(file_path)
    try:
        if len(text.strip()) < _MIN_TEXT_CHARS:
            ocr_pages = set(range(len(pdf)))
        else:
            ocr_pages = {i for i, page in enumerate(pdf) if _has_picture(page)}
        if not ocr_pages:
            return text  # plain text PDF: unchanged markitdown path, no vision cost
        if len(ocr_pages) > MAX_PAGES:
            raise ValueError(
                f"This PDF has {len(ocr_pages)} pages that need OCR; at most {MAX_PAGES} are supported. "
                "Split it and upload the parts."
            )
        # ponytail: sequential calls, ~5s/page; run pages concurrently if big scans get slow.
        parts = [
            llm.transcribe_image(_to_png(page.render(scale=_RENDER_SCALE).to_pil()))
            if i in ocr_pages
            else page.get_textpage().get_text_range()
            for i, page in enumerate(pdf)
        ]
    finally:
        pdf.close()
    return "\n\n".join(part.strip() for part in parts if part.strip())
