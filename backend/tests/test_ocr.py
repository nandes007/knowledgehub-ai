import ctypes
import io

import pypdfium2 as pdfium
import pytest
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from ingestion.index import VectorStore
from ingestion.ocr import MAX_PAGES, image_to_markdown, office_to_markdown, pdf_to_markdown
from ingestion.pipeline import ingest_file

_TEXT = "Employees get 20 days of PTO per year."


class _VisionLLM:
    def __init__(self) -> None:
        self.pages: list[bytes] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def transcribe_image(self, png: bytes) -> str:
        self.pages.append(png)
        return f"OCR page {len(self.pages)}: ```php\ndispatchSync();\n```"


def _add_text(pdf, page, text):
    obj = pdfium.raw.FPDFPageObj_NewTextObj(pdf.raw, b"Helvetica", 12.0)
    buffer = ctypes.create_string_buffer(text.encode("utf-16-le") + b"\0\0")
    pdfium.raw.FPDFText_SetText(obj, ctypes.cast(buffer, ctypes.POINTER(pdfium.raw.FPDF_WCHAR)))
    pdfium.raw.FPDFPageObj_Transform(obj, 1, 0, 0, 1, 50, 700)
    pdfium.raw.FPDFPage_InsertObject(page.raw, obj)


def _add_picture(pdf, page, width, height):
    image = pdfium.PdfImage.new(pdf)
    image.set_bitmap(pdfium.PdfBitmap.from_pil(Image.new("RGB", (50, 50), "gray")))
    image.set_matrix(pdfium.PdfMatrix().scale(width, height).translate(50, 50))
    page.insert_obj(image)


def _pdf(path, pages):
    """pages: list of (text or None, picture (w, h) in points or None)."""
    pdf = pdfium.PdfDocument.new()
    for text, picture in pages:
        page = pdf.new_page(612, 792)
        if text:
            _add_text(pdf, page, text)
        if picture:
            _add_picture(pdf, page, *picture)
        page.gen_content()
    pdf.save(path)


def _ingest(file_path, llm, tmp_path):
    return ingest_file(
        file_path,
        document_id="doc-1",
        company_id="comp-1",
        user_id="u1",
        filename=file_path.name,
        llm=llm,
        vector_store=VectorStore(persist_dir=str(tmp_path / "qdrant")),
    )


def test_image_upload_is_transcribed_by_the_vision_model(tmp_path):
    file_path = tmp_path / "scan.jpg"
    Image.new("RGB", (4000, 1000), "white").save(file_path)
    llm = _VisionLLM()

    assert _ingest(file_path, llm, tmp_path) >= 1
    assert len(llm.pages) == 1
    assert max(Image.open(io.BytesIO(llm.pages[0])).size) == 2048


def test_mixed_pdf_ocrs_only_pages_with_pictures(tmp_path):
    file_path = tmp_path / "guide.pdf"
    _pdf(
        file_path,
        [
            (_TEXT, None),  # text only: read directly
            ("See the screenshot below.", (500, 150)),  # code screenshot: OCR
            (_TEXT, (30, 30)),  # tiny logo: decoration, read directly
        ],
    )
    llm = _VisionLLM()

    text = pdf_to_markdown(file_path, llm)

    assert len(llm.pages) == 1
    assert text.count(_TEXT) == 2
    assert "dispatchSync();" in text
    assert text.index(_TEXT) < text.index("OCR page 1") < text.rindex(_TEXT)  # page order kept


def test_text_only_pdf_and_markdown_never_reach_the_vision_model(tmp_path):
    llm = _VisionLLM()
    pdf_path = tmp_path / "policy.pdf"
    _pdf(pdf_path, [(_TEXT, None)])
    md_path = tmp_path / "policy.md"
    md_path.write_text(f"# Policy\n\n{_TEXT}")

    assert _TEXT in pdf_to_markdown(pdf_path, llm)
    _ingest(md_path, llm, tmp_path)
    assert llm.pages == []


def test_scanned_pdf_is_ocrd_on_every_page(tmp_path):
    file_path = tmp_path / "scan.pdf"
    pages = [Image.new("RGB", (600, 800), "white") for _ in range(3)]
    pages[0].save(file_path, save_all=True, append_images=pages[1:])  # image-only PDF, no text layer
    llm = _VisionLLM()

    assert _ingest(file_path, llm, tmp_path) >= 1
    assert len(llm.pages) == 3


def test_corrupt_image_and_oversized_scan_give_clear_errors(tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="image may be corrupted"):
        image_to_markdown(broken, _VisionLLM())

    big = tmp_path / "big.pdf"
    pages = [Image.new("RGB", (10, 10)) for _ in range(MAX_PAGES + 1)]
    pages[0].save(big, save_all=True, append_images=pages[1:])
    llm = _VisionLLM()
    with pytest.raises(ValueError, match="at most"):
        pdf_to_markdown(big, llm)
    assert llm.pages == []


def test_office_images_are_transcribed_in_place_and_icons_skipped(tmp_path):
    screenshot, icon = tmp_path / "query.png", tmp_path / "icon.png"
    Image.new("RGB", (800, 400), "navy").save(screenshot)
    Image.new("RGB", (32, 32), "red").save(icon)
    deck = Presentation()
    for title, picture in [("Query used", screenshot), ("Same query again", screenshot), ("Contact", icon)]:
        slide = deck.slides.add_slide(deck.slide_layouts[5])
        slide.shapes.title.text = title
        slide.shapes.add_picture(str(picture), Inches(1), Inches(2))  # below the title
    file_path = tmp_path / "deck.pptx"
    deck.save(file_path)
    llm = _VisionLLM()

    text = office_to_markdown(file_path, llm)

    assert len(llm.pages) == 1  # repeated screenshot read once, icon skipped
    assert text.count("dispatchSync();") == 2
    assert text.index("Query used") < text.index("dispatchSync();") < text.index("Contact")
    assert "data:image" not in text  # no base64 left to pollute chunks
