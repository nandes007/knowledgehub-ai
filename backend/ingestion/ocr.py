"""Vision-model OCR for scanned PDFs, PDF pages with pictures, images embedded in
DOCX/PPTX, and image uploads.

Pages that need it are rendered to PNG and transcribed to markdown by the vision
model, one call per page, so the result flows through the normal chunk/embed path.
"""

import base64
import binascii
import io
import re
from dataclasses import dataclass
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
# ponytail: tuning knob. Embedded DOCX/PPTX images below this many pixels (about 150x150)
# are treated as icons and dropped instead of sent to the vision model.
_MIN_EMBEDDED_PIXELS = 150 * 150
_DATA_URI_IMAGE = re.compile(r"!\[[^\]]*\]\(data:image/[\w.+-]+;base64,([A-Za-z0-9+/=]+)\)")
# Marks where a kept picture sat in the markdown; the pipeline moves it off the chunk text
# into the chunk's image list, so it never reaches embeddings or keyword search.
IMAGE_MARKER = re.compile(r"<<img:(\d+)>>")


@dataclass
class ExtractedImage:
    png: bytes
    caption: str
    page: int | None = None


def _keep(images: list[ExtractedImage] | None, png: bytes, caption: str, page: int | None = None) -> str:
    """Collect a picture worth showing in answers; returns its marker ("" when not collecting)."""
    if images is None:
        return ""
    images.append(ExtractedImage(png=png, caption=caption, page=page))
    return f"<<img:{len(images) - 1}>>\n"


def _with_markers(markers: str, text: str) -> str:
    """The chunker splits at headings, so markers placed before a leading heading would
    land in the previous section, i.e. on the wrong chunk. Put them just under it."""
    first, _, rest = text.partition("\n")
    if markers and first.lstrip().startswith("#"):
        return f"{first}\n{markers}{rest}"
    return markers + text


def to_png(image: Image.Image) -> bytes:
    image = ImageOps.exif_transpose(image).convert("RGB")  # phone photos carry rotation in EXIF
    image.thumbnail((_MAX_SIDE, _MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def image_to_markdown(file_path: Path, llm: LLMProvider, images: list[ExtractedImage] | None = None) -> str:
    try:
        with Image.open(file_path) as image:
            png = to_png(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Couldn't read '{file_path.name}' — the image may be corrupted.") from exc
    text = llm.transcribe_image(png).strip()
    return _with_markers(_keep(images, png, text), text)


def _pictures(page: pdfium.PdfPage) -> list[tuple[float, float, float, float]]:
    """Bounds (left, bottom, right, top) of the pictures big enough not to be decoration."""
    width, height = page.get_size()
    bounds = []
    for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
        left, bottom, right, top = obj.get_bounds()
        if (right - left) * (top - bottom) >= _MIN_PICTURE_AREA * width * height:
            bounds.append((left, bottom, right, top))
    return bounds


def _crop_picture(page: pdfium.PdfPage, bounds: tuple[float, float, float, float]) -> bytes:
    # ponytail: bitmap picture objects only; vector-drawn diagrams (draw.io/Visio exports)
    # have no image object and are not kept. Render vector-heavy regions if that matters.
    width, height = page.get_size()
    left, bottom, right, top = (max(0.0, b) for b in bounds)
    crop = (left, bottom, max(0.0, width - right), max(0.0, height - top))
    return to_png(page.render(scale=_RENDER_SCALE, crop=crop).to_pil())


def pdf_to_markdown(file_path: Path, llm: LLMProvider, images: list[ExtractedImage] | None = None) -> str:
    """Text pages are read directly; pages with pictures go to the vision model whole.

    A PDF with no text at all (a scan) is OCR'd on every page.
    """
    text = convert_to_markdown(file_path)  # also rejects corrupt PDFs with a clear error
    pdf = pdfium.PdfDocument(file_path)
    try:
        if len(text.strip()) < _MIN_TEXT_CHARS:
            ocr_pages = set(range(len(pdf)))
        else:
            ocr_pages = {i for i, page in enumerate(pdf) if _pictures(page)}
        if not ocr_pages:
            return text  # plain text PDF: unchanged markitdown path, no vision cost
        if len(ocr_pages) > MAX_PAGES:
            raise ValueError(
                f"This PDF has {len(ocr_pages)} pages that need OCR; at most {MAX_PAGES} are supported. "
                "Split it and upload the parts."
            )
        # ponytail: sequential calls, ~5s/page; run pages concurrently if big scans get slow.
        parts = []
        for i, page in enumerate(pdf):
            if i not in ocr_pages:
                parts.append(page.get_textpage().get_text_range())
                continue
            text = llm.transcribe_image(to_png(page.render(scale=_RENDER_SCALE).to_pil())).strip()
            markers = "".join(_keep(images, _crop_picture(page, b), text, page=i + 1) for b in _pictures(page))
            parts.append(_with_markers(markers, text))
    finally:
        pdf.close()
    return "\n\n".join(part.strip() for part in parts if part.strip())


def office_to_markdown(file_path: Path, llm: LLMProvider, images: list[ExtractedImage] | None = None) -> str:
    """DOCX/PPTX text with each embedded picture replaced, in place, by its transcription."""
    text = convert_to_markdown(file_path, keep_data_uris=True)
    embedded = set(_DATA_URI_IMAGE.findall(text))
    if len(embedded) > MAX_PAGES:
        raise ValueError(
            f"This document has {len(embedded)} images to read; at most {MAX_PAGES} are supported. "
            "Split it and upload the parts."
        )
    transcribed: dict[str, str] = {}  # the same picture repeated (e.g. a logo) is read once
    markers: dict[str, str] = {}

    def replace(match: re.Match) -> str:
        data = match[1]
        if data not in transcribed:
            png, text = _transcribe_embedded(data, llm)
            transcribed[data] = text
            markers[data] = _keep(images, png, text) if png and text else ""
        return f"\n\n{markers[data]}{transcribed[data]}\n\n" if transcribed[data] else ""

    return _DATA_URI_IMAGE.sub(replace, text)


def _transcribe_embedded(data: str, llm: LLMProvider) -> tuple[bytes | None, str]:
    try:
        with Image.open(io.BytesIO(base64.b64decode(data))) as image:
            if image.width * image.height < _MIN_EMBEDDED_PIXELS:
                return None, ""
            png = to_png(image)
    except (UnidentifiedImageError, OSError, binascii.Error):
        return None, ""  # e.g. Windows EMF/WMF clip art Pillow can't open: skip it, keep the document
    return png, llm.transcribe_image(png).strip()
