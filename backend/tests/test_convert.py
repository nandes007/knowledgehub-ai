import pytest

from ingestion.convert import convert_to_markdown


def test_converts_markdown_file_to_text(tmp_path):
    file_path = tmp_path / "sample.md"
    file_path.write_text("# Hello\n\nWorld")

    result = convert_to_markdown(file_path)

    assert "Hello" in result
    assert "World" in result


def test_corrupt_file_raises_a_clear_error_instead_of_the_raw_library_exception(tmp_path):
    file_path = tmp_path / "broken.pdf"
    file_path.write_bytes(b"%PDF-1.4\n%not a real pdf body\nendobj\ntrailer\n")

    with pytest.raises(ValueError, match="corrupted or in an unsupported format"):
        convert_to_markdown(file_path)
