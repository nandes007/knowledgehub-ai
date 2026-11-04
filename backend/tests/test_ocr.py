import io

import pytest
from PIL import Image

from ingestion.index import VectorStore
from ingestion.ocr import MAX_PAGES, page_images
from ingestion.pipeline import ingest_file


class _VisionLLM:
    def __init__(self) -> None:
        self.pages: list[bytes] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def transcribe_image(self, png: bytes) -> str:
        self.pages.append(png)
        return f"# Page {len(self.pages)}\n\nEmployees get 20 days of PTO per year."


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


def test_scanned_pdf_falls_back_to_ocr_page_by_page(tmp_path):
    file_path = tmp_path / "scan.pdf"
    pages = [Image.new("RGB", (600, 800), "white") for _ in range(3)]
    pages[0].save(file_path, save_all=True, append_images=pages[1:])  # image-only PDF, no text layer
    llm = _VisionLLM()

    assert _ingest(file_path, llm, tmp_path) >= 1
    assert len(llm.pages) == 3


def test_text_documents_never_reach_the_vision_model(tmp_path):
    file_path = tmp_path / "policy.md"
    file_path.write_text("# Policy\n\nEmployees get 20 days of PTO per year.")
    llm = _VisionLLM()

    _ingest(file_path, llm, tmp_path)
    assert llm.pages == []


def test_corrupt_image_and_oversized_pdf_give_clear_errors(tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="image may be corrupted"):
        list(page_images(broken))

    big = tmp_path / "big.pdf"
    pages = [Image.new("RGB", (10, 10)) for _ in range(MAX_PAGES + 1)]
    pages[0].save(big, save_all=True, append_images=pages[1:])
    with pytest.raises(ValueError, match="OCR supports at most"):
        list(page_images(big))
