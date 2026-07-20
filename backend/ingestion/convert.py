from pathlib import Path

from markitdown import MarkItDown

_converter = MarkItDown()


def convert_to_markdown(file_path: Path) -> str:
    """Convert a PDF/DOCX/PPTX/MD file to markdown text."""
    try:
        result = _converter.convert(str(file_path))
    except Exception as exc:
        raise ValueError(
            f"Couldn't read '{file_path.name}' — the file may be corrupted or in an unsupported format."
        ) from exc
    return result.text_content
