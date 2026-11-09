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


def test_scanned_pdf_reports_progress_per_ocrd_page(tmp_path):
    file_path = tmp_path / "scan.pdf"
    pages = [Image.new("RGB", (600, 800), "white") for _ in range(2)]
    pages[0].save(file_path, save_all=True, append_images=pages[1:])
    reported: list[int] = []

    ingest_file(
        file_path,
        document_id="doc-1",
        company_id="comp-1",
        user_id="u1",
        filename=file_path.name,
        llm=_VisionLLM(),
        vector_store=VectorStore(persist_dir=str(tmp_path / "qdrant")),
        on_progress=reported.append,
    )

    # One tick per OCR'd page inside the extract step, then one per later step.
    assert reported == [35, 70, 70, 75, 90, 95]


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


# --- Pictures kept for answers ---------------------------------------------------------


def _deck(tmp_path):
    screenshot, icon = tmp_path / "flow.png", tmp_path / "icon.png"
    Image.new("RGB", (800, 400), "navy").save(screenshot)
    Image.new("RGB", (32, 32), "red").save(icon)
    deck = Presentation()
    for title, picture in [("Deploy flow", screenshot), ("Again", screenshot), ("Contact", icon)]:
        slide = deck.slides.add_slide(deck.slide_layouts[5])
        slide.shapes.title.text = title
        slide.shapes.add_picture(str(picture), Inches(1), Inches(2))
    file_path = tmp_path / "deck.pptx"
    deck.save(file_path)
    return file_path


def test_office_pictures_are_kept_once_and_icons_skipped(tmp_path):
    images = []

    office_to_markdown(_deck(tmp_path), _VisionLLM(), images)

    assert len(images) == 1  # repeated diagram saved once, icon dropped
    assert Image.open(io.BytesIO(images[0].png)).size == (800, 400)
    assert "dispatchSync();" in images[0].caption


def test_pdf_pictures_are_cropped_to_the_picture_not_the_page(tmp_path):
    file_path = tmp_path / "guide.pdf"
    _pdf(file_path, [(_TEXT, None), ("See the diagram.", (300, 150))])
    images = []

    pdf_to_markdown(file_path, _VisionLLM(), images)

    assert len(images) == 1 and images[0].page == 2
    width, height = Image.open(io.BytesIO(images[0].png)).size
    assert (abs(width - 600), abs(height - 300)) <= (4, 4)  # 300x150pt at 2x, not the 612x792pt page


def test_text_only_pdf_keeps_no_pictures(tmp_path):
    file_path = tmp_path / "policy.pdf"
    _pdf(file_path, [(_TEXT, None)])
    images = []
    llm = _VisionLLM()

    pdf_to_markdown(file_path, llm, images)

    assert images == [] and llm.pages == []


def test_standalone_image_document_is_its_own_picture(tmp_path):
    file_path = tmp_path / "diagram.png"
    Image.new("RGB", (400, 300), "white").save(file_path)
    images = []

    image_to_markdown(file_path, _VisionLLM(), images)

    assert len(images) == 1 and images[0].caption.startswith("OCR page 1")


def test_chunks_carry_their_picture_and_no_marker_reaches_the_index(tmp_path):
    store = VectorStore(persist_dir=str(tmp_path / "qdrant"))
    images = []
    ingest_file(
        _deck(tmp_path),
        document_id="doc-1",
        company_id="comp-1",
        user_id="u1",
        filename="deck.pptx",
        llm=_VisionLLM(),
        vector_store=store,
        images=images,
    )

    chunks = store.query([1.0, 0.0], top_k=50)
    assert all("<<img:" not in c["text"] for c in chunks)
    with_picture = [c for c in chunks if c["images"]]
    assert with_picture and with_picture[0]["images"][0]["index"] == 0
    assert "dispatchSync();" in with_picture[0]["images"][0]["caption"]


def test_each_picture_lands_on_its_own_pages_chunk_when_pages_start_with_a_heading(tmp_path):
    class _HeadedPages(_VisionLLM):
        def transcribe_image(self, png: bytes) -> str:
            self.pages.append(png)
            return f"## Step {len(self.pages)}\n\nDiagram for step {len(self.pages)}."

    file_path = tmp_path / "guide.pdf"
    _pdf(file_path, [(_TEXT, None), ("Step 1", (300, 150)), ("Step 2", (300, 150))])
    store = VectorStore(persist_dir=str(tmp_path / "qdrant"))
    ingest_file(
        file_path,
        document_id="doc-1",
        company_id="comp-1",
        user_id="u1",
        filename="guide.pdf",
        llm=_HeadedPages(),
        vector_store=store,
        images=[],
    )

    by_text = {c["text"].split("\n")[0]: [i["index"] for i in c["images"]] for c in store.query([1.0, 0.0], top_k=50)}
    assert by_text == {_TEXT: [], "Step 1": [0], "Step 2": [1]}
