from pathlib import Path

from markitdown import MarkItDown

_converter = MarkItDown()


def convert_to_markdown(file_path: Path) -> str:
    """Convert a PDF/DOCX/PPTX/MD file to markdown text."""
    result = _converter.convert(str(file_path))
    return result.text_content
