from pathlib import Path

from markitdown import MarkItDown

_converter = MarkItDown()


def convert_to_markdown(file_path: Path, *, keep_data_uris: bool = False) -> str:
    """Convert a PDF/DOCX/PPTX/MD file to markdown text.

    keep_data_uris keeps embedded DOCX/PPTX images as full base64 data URIs; by default
    markitdown shortens them to an unusable "data:image/png;base64..." placeholder.
    """
    try:
        result = _converter.convert(str(file_path), keep_data_uris=keep_data_uris)
    except Exception as exc:
        raise ValueError(
            f"Couldn't read '{file_path.name}' — the file may be corrupted or in an unsupported format."
        ) from exc
    return result.text_content
